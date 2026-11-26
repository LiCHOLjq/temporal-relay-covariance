"""Structural diagnostics. Python 3.10+, standard library only."""
import argparse
import csv
import gzip
import hashlib
import io
import itertools
import json
import math
import statistics
import sys
from collections import Counter, defaultdict
from contextlib import contextmanager
from decimal import Decimal
from fractions import Fraction
from pathlib import Path

HERE = Path(__file__).resolve().parent
DATASETS = {
    'CollegeMsg': 'CollegeMsg.txt.gz',
    'EmailEU': 'email-Eu-core-temporal.txt.gz',
    'BitcoinOTC': 'soc-sign-bitcoinotc.csv.gz',
    'BitcoinAlpha': 'soc-sign-bitcoinalpha.csv.gz',
    'MathOverflowA2Q': 'sx-mathoverflow-a2q.txt.gz'
}
WIDTHS = (60, 3600, 86400)
MODES = ('all', 'odd', 'contrast')


def write_rows(path, rows):
    with path.open('w', encoding='utf-8', newline='') as stream:
        writer = csv.DictWriter(stream, list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


@contextmanager
def compressed_csv(path, fields):
    # A fixed timestamp makes repeated exports byte-identical.
    with path.open('wb') as target, gzip.GzipFile(fileobj=target, mode='wb', mtime=0, filename='') as compressed:
        with io.TextIOWrapper(compressed, encoding='utf-8', newline='') as stream:
            writer = csv.writer(stream)
            writer.writerow(fields)
            yield writer


def read_times(path):
    with gzip.open(path, 'rt') as stream:
        records = []
        digits = 0
        for s in stream:
            if not s.strip() or s.startswith('#'):
                continue
            parts = s.replace(',', ' ').split()
            t = Decimal(parts[-1])
            digits = max(digits, -t.as_tuple().exponent)
            records.append((t, int(parts[0]), int(parts[1])))
    scale = 10 ** digits
    return sorted((int(t * scale), u, v) for t, u, v in records), scale, digits


def describe_gaps(events, name, scope, scale, digits, gap_writer):
    stamps = sorted({t for t, _, _ in events})
    gaps = sorted(l-r for r, l in zip(stamps, stamps[1:]))
    def seconds(val):
        return format(Decimal(val)/scale,'f')
    for gap, count in sorted(Counter(gaps).items()):
        gap_writer.writerow((name, scope, seconds(gap), count))
    return dict(dataset=name, scope=scope, contacts=len(events), distinct_times=len(stamps),
                max_fraction_digits=digits, gaps=len(gaps), minimum_s=seconds(gaps[0]),
                median_s=seconds(statistics.median(map(Decimal, gaps))),
                p95_s=seconds(gaps[math.ceil(.95*len(gaps))-1]), maximum_s=seconds(gaps[-1]),
                unit24h_gaps=sum(x == 86400*scale for x in gaps),
                distinct_day_phases=len({t % (86400*scale) for t in stamps}),
                first_day_phase_s=seconds(stamps[0] % (86400*scale)))


def moment_terms(group, full):
    """Return m, sum (A-B)^2, sum AB and optional numerators for the other two queries."""
    n = Counter((u,v) for _,u,v in group)
    incoming, outgoing = Counter(), Counter()
    for (u,v), copies in n.items():
        incoming[v] += copies
        outgoing[u] += copies
    m = square = product = 0
    # Four integer moments per group query: 2E, 12Var, 12V_pair, 12V_diag.
    modes = [[0,0,0,0] for _ in range(2)] if full else None
    for (u,v), copies in n.items():
        rev = n[v,u]
        a, b = outgoing[v]-rev, incoming[u]-rev
        m += copies * a
        square += copies * (a-b)**2
        product += copies*a*b
        if full:
            for dst, wu, wv in [(modes[0],u%2,v%2),(modes[1],2*(u%2)-1,2*(v%2)-1)]:
                mass = copies*a*wv**2
                dst[0] += copies*a*wv
                dst[1] += mass + copies*(a*wv-b*wu)**2
                dst[2] += 3*mass
                dst[3] += mass + copies*((a*wv)**2+(b*wu)**2)
    return m, square, product, modes


def ordered_native(records):
    """Direct eligible-pair enumeration with an explicit tie count."""
    by_source = defaultdict(list)
    for t,u,v in records:
        by_source[u].append((t,v))
    earlier = later = tied = 0
    for t,u,v in records:
        for s,w in by_source[v]:
            if u != w:
                earlier += t < s
                later += t > s
                tied += t == s
    return earlier,later,tied


def collect(events, scale, name, width, phase, bucket_writer, candidates):
    base = phase == 0
    hourly = base and width == 3600
    buckets = []
    grouped = [[0]*4 for _ in MODES]
    earlier = later = tied = 0
    for bucket, it in itertools.groupby(events,lambda r:(r[0]-phase*scale)//(width*scale)):
        records = list(it)
        m, sq, prod, modes = moment_terms(records,base)
        v12 = m+sq
        buckets.append((bucket,len(records),m,v12,prod))
        if base:
            if bucket in candidates:
                row = candidates[bucket]
                contrast12 = modes[1][1]
                assert 2*contrast12 == row['var24'] and v12+contrast12 == row['ablated24']
            vectors = [(m,v12,3*m,v12+2*prod)]+modes
            for total,values in zip(grouped,vectors):
                for j,x in enumerate(values):
                    total[j]+=x
            bucket_writer.writerow((name,width,bucket,len(records),m,sq,prod,v12))
        if hourly:
            a,b,c=ordered_native(records)
            assert a+b+c==m
            earlier+=a; later+=b; tied+=c
    m=sum(row[2] for row in buckets)
    v12=sum(row[3] for row in buckets)
    prod=sum(row[4] for row in buckets)
    diag12=v12+2*prod
    sum_m2=sum(row[2]**2 for row in buckets)
    assert m<=v12<=sum_m2+2*m
    by_pairs=sorted(buckets,key=lambda x:(-x[2],x[0]))
    k=(len(buckets)+99)//100
    top=by_pairs[:k]
    nvar_h=sum(row[3] for row in top)
    result=dict(dataset=name,width_s=width,phase_s=phase,contacts=len(events),occupied=len(buckets),
                positive=sum(row[2]>0 for row in buckets),max_pairs=by_pairs[0][2],
                m=m,sum_m_squared=sum_m2,sum_role_square=v12-m,sum_pred_succ=prod,var12=v12,
                pair12=3*m,diag12=diag12,mean_weighted_m=(sum_m2/m if m else None),pairs_per_contact=m/len(events),
                q=((v12-m)/m if m else None),p=(prod/m if m else None),pair_ratio=(3*m/v12 if m else None),
                diag_ratio=(diag12/v12 if m else None),top1_n=k,top1_min_pairs=top[-1][2],
                top1_pairs=sum(row[2] for row in top),top1_var12=nvar_h,
                partition_sha256=hashlib.sha256(','.join(str(row[1]) for row in buckets).encode('ascii')).hexdigest())
    native=None
    if hourly:
        assert m>0
        difference2=earlier-later
        native=dict(dataset=name,eligible=m,earlier=earlier,later=later,ties=tied,mu=m/2,
                    native=earlier+tied/2,sd=math.sqrt(v12/12),relative_gap=difference2/m,
                    relative_sd=2*math.sqrt(v12/12)/m,z=difference2/(2*math.sqrt(v12/12)))
    group_rows = []
    if base:
        for mode,(mu,va,pa,di) in zip(MODES,grouped):
            group_rows.append(dict(dataset=name,width_s=width,query=mode,mean2=mu,var12=va,pair12=pa,diag12=di))
    return result, native, group_rows


def compare_ranks(records):
    stats=Counter()
    for a,b in itertools.combinations(records,2):
        dx=a['var24']-b['var24']
        dy=a['ablated24']-b['ablated24']
        kind=('both_tied' if dx==dy==0 else 'full_only_tied' if dx==0 else
              'ablated_only_tied' if dy==0 else 'concordant' if dx*dy>0 else 'discordant')
        stats[kind]+=1
    c,d=stats['concordant'],stats['discordant']
    denom=math.sqrt((c+d+stats['full_only_tied'])*(c+d+stats['ablated_only_tied']))
    return dict(windows=len(records),comparisons=len(records)*(len(records)-1)//2,
                tau_b=(c-d)/denom,**{k:stats[k] for k in
                ['concordant','discordant','full_only_tied','ablated_only_tied','both_tied']})


def check_and_export(artifact, out, group_rows, native_rows):
    results=artifact/'experiments'/'results'
    legacy={(r['dataset'],int(r['width']),r['query']):r for r in csv.DictReader((results/'moments.csv').open())}
    sql=json.loads((results/'sql.json').read_text())['datasets']['MathOverflowA2Q']['moments']
    checks=0
    for r in group_rows:
        k=r['dataset'],r['width_s'],r['query']
        actual=tuple(r[x] for x in ['mean2','var12','pair12','diag12'])
        if k in legacy:
            old=legacy[k]
            expect=(int(float(old['mean'])*2),int(old['var12']),int(old['iid_var12']),int(old['diagonal_var12']))
        elif k[1]==3600:
            old=sql[k[2]]
            expect=tuple(old[a] for a in ['mean2','var12','iid12','diag12'])
        else:
            continue
        assert expect==actual,k
        checks+=1
    for r in native_rows:
        name=r['dataset']
        old=(sql['all']['native_mean2']/2 if name=='MathOverflowA2Q' else float(legacy[name,3600,'all']['native_mean']))
        assert r['native']==old
    windows=json.loads((results/'candidate_check.json').read_text())['widths']
    ranks=[dict(width_s=width,**compare_ranks(w['records'])) for width,w in windows.items()]
    write_rows(out/'window_ranks.csv',ranks)
    shuffle=json.loads((results/'shuffle.json').read_text())
    precision=[]
    for w in shuffle:
        vals=w['sample_counts']; n=len(vals);sx=sum(vals);sxx=sum(x*x for x in vals)
        # Each leave-one-out sample variance has this same denominator.
        denom=(n-1)*(n-2)
        deleted=[(n-1)*(sxx-x*x)-(sx-x)**2 for x in vals]
        centered=n*sum(x*x for x in deleted)-sum(deleted)**2
        jack_se=math.sqrt(Fraction((n-1)*centered, n*n*denom*denom))
        var=statistics.variance(vals)
        precision.append(dict(dataset=w['dataset'],replicates=n,sample_over_exact=var/w['exact'],
                              jackknife_se_over_exact=jack_se/w['exact']))
    write_rows(out/'shuffle_precision.csv',precision)
    return dict(archived_four_moment_rows_matched=checks,hourly_native_counts_matched=len(native_rows),
                rank_windows_checked=sum(r['windows'] for r in ranks),shuffle_checks=len(shuffle))


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--artifact',type=Path,default=HERE.parents[2]/'artifact')
    ap.add_argument('--data',type=Path,help='Folder containing five hash-matched SNAP .gz files')
    ap.add_argument('--out',type=Path,default=HERE/'results')
    args=ap.parse_args()
    data=args.data or args.artifact/'experiments'/'data'
    out=args.out
    out.mkdir(parents=True,exist_ok=True)
    expected={Path(row['path']).name:row['sha256'] for row in json.loads((args.artifact/'snap_sources.json').read_text())}
    hashes={}
    for name in DATASETS.values():
        hashes[name]=hashlib.sha256((data/name).read_bytes()).hexdigest()
        if hashes[name]!=expected[name]:
            raise ValueError('Source checksum mismatch: '+name)
    sampled=json.loads((args.artifact/'experiments/results/candidate_check.json').read_text())['widths']
    by_width={int(width):{r['bucket']:r for r in val['records']} for width,val in sampled.items()}
    aligned,phases,gaps,native,group_rows=[],[],[],[],[]
    with compressed_csv(out/'buckets.csv.gz',('dataset','width_s','bucket','contacts','m','sum_role_square','sum_pred_succ','var12')) as bw:
        with compressed_csv(out/'gap_histogram.csv.gz',('dataset','scope','gap_s','frequency')) as gw:
            for name,filename in DATASETS.items():
                raw,scale,digits=read_times(data/filename)
                events=[r for r in raw if r[1]!=r[2]]
                for scope,records in [('released',raw),('analysis',events)]:
                    gaps.append(describe_gaps(records,name,scope,scale,digits,gw))
                for width in WIDTHS:
                    for phase in (0,width//4,width//2,3*width//4):
                        candidates=by_width[width] if name=='CollegeMsg' and phase==0 else {}
                        summary,nat,rows=collect(events,scale,name,width,phase,bw,candidates)
                        phases.append(summary)
                        if not phase:aligned.append(summary)
                        if nat:native.append(nat)
                        group_rows.extend(rows)
                print(name,flush=True)
    for filename,rows in [('width_statistics',aligned),('phase_statistics',phases),('timestamp_gaps',gaps),
                           ('native_replay',native),('query_moments',group_rows)]:
        write_rows(out/(filename+'.csv'),rows)
    assert len({r['partition_sha256'] for r in phases if r['dataset']=='BitcoinAlpha'})==1
    checks=check_and_export(args.artifact,out,group_rows,native)
    checks.update(inputs_sha256=hashes,aligned_width_cells=len(aligned),phase_width_cells=len(phases),
                  all_query_width_cells=len(group_rows),python=sys.version.split()[0])
    (out/'checks.json').write_text(json.dumps(checks,indent=2)+'\n',encoding='utf-8')


if __name__=='__main__':
    main()

