"""Run from an isolated directory containing data/*.gz. Python 3.10+, standard library."""
import csv
import gzip
import hashlib
import itertools
import json
import math
import os
import platform
import random
import statistics
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path


SOURCES = {
    'CollegeMsg': 'CollegeMsg.txt.gz',
    'EmailEU': 'email-Eu-core-temporal.txt.gz',
    'BitcoinOTC': 'soc-sign-bitcoinotc.csv.gz',
    'BitcoinAlpha': 'soc-sign-bitcoinalpha.csv.gz',
}
MODES = ('all', 'odd', 'contrast')


def weight(v, mode):
    if mode == 'all':
        return 1
    return (v % 2) if mode == 'odd' else (2 * (v % 2) - 1)


def endpoint(edges, mode):
    """Return 2*mean, 12*variance, 12*independent-pair and 12*diagonal baselines."""
    counts = Counter(edges)
    inc, out = Counter(), Counter()
    for (u, v), n in counts.items():
        inc[v] += n
        out[u] += n
    mean2 = mass = squares = marginal = 0
    for (u, v), n in counts.items():
        rev = counts[v, u]
        a = out[v] - rev
        b = inc[u] - rev
        w = weight(v, mode)
        left, right = w * a, weight(u, mode) * b
        mean2 += n * w * a
        mass += n * w * w * a
        squares += n * (left - right) ** 2
        marginal += n * (left * left + right * right)
    return mean2, mass + squares, 3 * mass, mass + marginal


def explicit(edges, mode):
    """Construct arc contributions by visiting actual join outputs; stores only divergences."""
    by_src = defaultdict(list)
    for j, (u, v) in enumerate(edges):
        by_src[u].append((j, v))
    div = [0] * len(edges)
    mass = total = 0
    for i, (u, v) in enumerate(edges):
        w = weight(v, mode)
        for j, z in by_src[v]:
            if z != u:
                total += w
                mass += w*w
                div[i] += w
                div[j] -= w
    return total, mass + sum(d*d for d in div)


def ordered(edges, mode):
    """Scan one realized order and count all earlier compatible first events."""
    incoming, seen = Counter(), Counter()
    total = 0
    for u, v in edges:
        total += weight(u, mode) * (incoming[u] - seen[v, u])
        incoming[v] += 1
        seen[u, v] += 1
    return total


def literal(edges, mode):
    return sum(weight(v, mode) for i, (u, v) in enumerate(edges)
               for y, z in edges[i+1:] if v == y and u != z)


def exhaustive():
    rng = random.Random(9127)
    universe = list(itertools.permutations(range(4), 2))
    cases = [[], [(0,1)]*5, [(0,1),(1,0),(1,2),(2,0),(0,1)],
             [(0,1),(1,2),(2,0)], [(0,1),(1,2),(2,3)]]
    cases += [rng.choices(universe, k=n) for n in range(2,8) for _ in range(6)]
    checks = orders = 0
    for edges, mode in itertools.product(cases, MODES):
        mu2, var12, _, _ = endpoint(edges, mode)
        n = s = ss = 0
        for perm in itertools.permutations(edges):
            x = literal(perm, mode)
            n += 1
            s += x
            ss += x*x
        assert 2*s == n*mu2 and 12*(ss*n-s*s) == n*n*var12
        checks += 1
        orders += n
    return dict(bins=len(cases), queries=checks, permutations_including_weights=orders)


def load(path):
    events = []
    dropped = 0
    with gzip.open(path, 'rt') as f:
        for line in f:
            if line.startswith('#') or not line.strip():
                continue
            parts = line.replace(',', ' ').split()
            u, v = map(int, parts[:2])
            if u == v:
                dropped += 1
            else:
                # SNAP Bitcoin timestamps can be decimal strings. Keep native resolution.
                events.append((float(parts[-1]), u, v))
    events.sort(key=lambda row: row[0])
    return events, dropped


def native_mean2(records, mode):
    incoming, seen = Counter(), Counter()
    total2 = 0
    for _, group in itertools.groupby(records, key=lambda x: x[0]):
        edges = [(u,v) for _,u,v in group]
        for u, v in edges:
            total2 += 2 * weight(u, mode) * (incoming[u] - seen[v,u])
        if len(edges) > 1:
            total2 += endpoint(edges, mode)[0]
        for u, v in edges:
            incoming[v] += 1
            seen[u,v] += 1
    return total2


def timed(call):
    start = time.perf_counter()
    value = call()
    return value, time.perf_counter() - start


def benchmark(bins, repeats):
    times = defaultdict(list)
    for r in range(repeats):
        algs = (endpoint, explicit) if r % 2 == 0 else (explicit, endpoint)
        for alg in algs:
            _, elapsed = timed(lambda: [alg(edges, 'all') for edges in bins])
            times[alg.__name__].append(elapsed)
    return dict(times)


def main():
    root = Path('results')
    root.mkdir(exist_ok=True)
    meta = dict(python=sys.version, platform=platform.platform(), affinity=sorted(os.sched_getaffinity(0))
                if hasattr(os,'sched_getaffinity') else None,
                exhaustive=exhaustive(), sources={}, hourly_checks=0,
                script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
    rows, timings, shuffles = [], {}, []
    for name, file in SOURCES.items():
        path = Path('data')/file
        (events, dropped), io = timed(lambda: load(path))
        meta['sources'][name] = dict(file=file, sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                                      events=len(events), dropped_self=dropped, read_sort_s=io,
                                      native_stamps=len({e[0] for e in events}))
        for width in (60,3600,86400):
            raw = [list(g) for _,g in itertools.groupby(events,key=lambda x: int(x[0]//width))]
            bins = [[(u,v) for _,u,v in g] for g in raw]
            for mode in MODES:
                vals = [endpoint(edges, mode) for edges in bins]
                if width == 3600:
                    assert all(val[:2] == explicit(edges,mode) for val,edges in zip(vals,bins))
                    meta['hourly_checks'] += len(vals)
                mu2, v12, ind12, diag12 = map(sum, zip(*vals))
                native2 = sum(native_mean2(g, mode) for g in raw)
                rows.append(dict(dataset=name,width=width,query=mode,bins=len(raw),
                                 informative_bins=sum(v[1]>0 for v in vals),mean=mu2/2,
                                 var12=v12, iid_var12=ind12, diagonal_var12=diag12,
                                 native_mean=native2/2,z=(native2-mu2)/2/math.sqrt(v12/12) if v12 else None))
            if width == 3600:
                timings[name] = benchmark(bins,5)
                # Uniformly choose up to 32 informative hourly bins, fixed seed. Replay actual events.
                pool = [i for i,b in enumerate(bins) if endpoint(b,'all')[1]>0]
                rng = random.Random(382)
                subset = [bins[i][:] for i in rng.sample(pool,min(32,len(pool)))]
                exact = sum(endpoint(b,'all')[1] for b in subset)/12
                simulations = []
                start = time.perf_counter()
                for _ in range(512):
                    for b in subset:
                        rng.shuffle(b)
                    simulations.append(sum(ordered(b,'all') for b in subset))
                shuffles.append(dict(dataset=name, informative_hour_sample=len(subset),replicates=len(simulations),
                                     exact=exact, sample_variance=statistics.variance(simulations),
                                     seconds=time.perf_counter()-start, sample_counts=simulations))
        print(name, 'complete', flush=True)
    stress = {}
    for k in (16,64,256,1024):
        # Hub with 2k unique spokes and k^2 valid pairs.
        bin_edges = [(i,0) for i in range(1,k+1)] + [(0,i) for i in range(k+1,2*k+1)]
        assert explicit(bin_edges,'all') == endpoint(bin_edges,'all')[:2]
        stress[k] = benchmark([bin_edges],5)
    with (root/'moments.csv').open('w',newline='') as f:
        writer=csv.DictWriter(f, fieldnames=rows[0])
        writer.writeheader()
        writer.writerows(rows)
    for filename, value in [('run.json',meta),('timings.json',timings),
                            ('shuffle.json',shuffles),('synthetic.json',stress)]:
        (root/filename).write_text(json.dumps(value,indent=2)+'\n')


if __name__ == '__main__':
    main()
