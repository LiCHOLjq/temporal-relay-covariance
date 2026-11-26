"""Derive the timing statistics and check the results against the integer bucket archive."""
import argparse
import csv
import gzip
import json
from collections import defaultdict
from fractions import Fraction
from pathlib import Path
from statistics import median, quantiles

HERE = Path(__file__).resolve().parent
EXP = HERE.parent
PROJECT = EXP.parent.parent
PRIMARY = ("CollegeMsg","EmailEU","BitcoinOTC","BitcoinAlpha")

def read_csv(path):
    with path.open(newline="",encoding="utf-8-sig") as stream:
        return list(csv.DictReader(stream))

def dump(path,rows):
    with path.open("w",newline="",encoding="utf-8") as stream:
        writer=csv.DictWriter(stream,fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

def summary(x):
    q1,_,q3=quantiles(x,n=4,method="inclusive")
    return median(x),q1,q3

def original_analysis(out):
    stats={(r["experiment"],r["dataset"],r["method"],int(r["n"]),r["phase"]):float(r["median_ms"])
           for r in read_csv(EXP/"timing/derived/summaries.csv")}
    sizes=json.loads((EXP/"timing/results/sizes.json").read_text())
    old=json.loads((PROJECT/"artifact/experiments/results/timings.json").read_text())
    results=[]
    for trace in PRIMARY:
        def v(method,phase):
            return stats["batch",trace,method,64,phase]
        count=sizes[trace]
        nt=count["cached_terms"]
        ne=count["diagonal"]+count["unordered_cross"]
        c,m=v("cache","evaluation"),v("matrix","evaluation")
        cb,mb=v("cache","build"),v("matrix","build")
        enumeration=stats["single",trace,"enumerate",1,"total"]
        legacy=1000*median(old[trace]["explicit"])
        results.append(dict(dataset=trace,eval_factor=c/m,total_factor=v("cache","total")/v("matrix","total"),
                            compression=nt/ne,matrix_build_pct=100*mb/v("matrix","total"),
                            cache_build_ms=cb,matrix_build_ms=mb,extra_matrix_build_ms=mb-cb,
                            cache_build_pct_of_matrix=100*cb/mb,cache_ns_per_term=c*1e6/(64*nt),
                            matrix_ns_per_entry=m*1e6/(64*ne),hourly_enumerate_ms=enumeration,
                            previous_enumerate_ms=legacy,enumeration_change_pct=100*(enumeration/legacy-1)))
    dump(out/"amortization.csv",results)

def daily_analysis(source,out):
    with gzip.open(EXP/"structure/results/buckets.csv.gz","rt",encoding="utf-8") as stream:
        buckets=defaultdict(list)
        for row in csv.DictReader(stream):
            width=int(row["width_s"])
            if width in (3600,86400):
                buckets[row["dataset"],width].append(tuple(int(row[k]) for k in ("bucket","contacts","m","var12")))
    traces=read_csv(source/"workloads.csv")
    times=read_csv(source/"raw_timings.csv")
    assert len(times)==24*len(traces)
    results=[]
    for t in traces:
        name=t["dataset"]
        width=int(t["width_s"])
        scope=t["scope"]
        b=buckets[name,width]
        if scope!="full":
            high_m=max(b,key=lambda r:(r[2],-r[0]))
            high_density=max(b,key=lambda r:(Fraction(r[2],r[1]),-r[0]))
            if scope in ("max_pairs","max_pairs_and_density"): assert int(t["bucket"])==high_m[0]
            if scope in ("max_density","max_pairs_and_density"): assert int(t["bucket"])==high_density[0]
            b=[r for r in b if r[0]==int(t["bucket"])]
        assert len(b)==int(t["occupied"])
        assert tuple(sum(r[i] for r in b) for i in (1,2,3))==tuple(int(t[k]) for k in ("contacts","m","var12"))
        rows=[r for r in times if r["dataset"]==name and int(r["width_s"])==width and r["scope"]==scope]
        data={}
        for method in ("enumerate","endpoint_exact"):
            subset=[r for r in rows if r["method"]==method]
            assert sorted(int(r["trial"]) for r in subset)==list(range(1,13))
            assert sum(r["position"]=="1" for r in subset)==6
            data[method]=summary([float(r["elapsed_ms"]) for r in subset])
        en,ep=data["enumerate"],data["endpoint_exact"]
        results.append(dict(**t,enum_ms=en[0],enum_q1_ms=en[1],enum_q3_ms=en[2],end_ms=ep[0],
                            end_q1_ms=ep[1],end_q3_ms=ep[2],enumeration_over_endpoint=en[0]/ep[0]))
    dump(out/"daily_summary.csv",results)
    logs=read_csv(source/"scheduler.csv")
    wall=sum(float(r["wall_s"]) for r in logs)
    wait=sum(float(r["runnable_wait_ms"]) for r in logs)
    summary_info=dict(workloads=len(traces),matched_bucket_entries=sum(int(t["occupied"]) for t in traces),
                      timing_rows=len(times),intervals=len(logs),monitored_wall_s=wall,runnable_wait_ms=wait,
                      runnable_wait_pct=wait/(10*wall),max_sibling_busy=max(float(r["sibling_max_busy"]) for r in logs))
    (out/"checks.json").write_text(json.dumps(summary_info,indent=2)+"\n")

if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source",type=Path,default=HERE/"results")
    parser.add_argument("--out",type=Path,default=HERE/"derived")
    args=parser.parse_args()
    args.out.mkdir(exist_ok=True,parents=True)
    original_analysis(args.out)
    daily_analysis(args.source,args.out)
