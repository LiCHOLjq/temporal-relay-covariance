"""CollegeMsg grouped-variance falsification, using an independent shuffle reference."""
from collections import defaultdict
from fractions import Fraction
from itertools import combinations
from math import sqrt
from pathlib import Path
import gc
import hashlib
import json
import os
import random
import statistics
import time
import tracemalloc

import benchmark as bm

SEED = 810232
N = 512
CAP = 16


def score_window(edges, seed):
    rng = random.Random(seed)
    stream = list(edges)
    mu2, v12 = bm.endpoint(edges, 'contrast')[:2]
    all12 = bm.endpoint(edges, 'all')[1]
    var24, ablated24 = 2 * v12, all12 + v12
    assert bm.explicit(edges, 'contrast') == (mu2, v12)
    raw = raw2 = err_full = err_ablated = 0
    for _ in range(N):
        rng.shuffle(stream)
        z = bm.ordered(stream, 'contrast')
        raw += z
        raw2 += z*z
        target24 = 6 * (2*z - mu2)**2
        err_full += (target24 - var24)**2
        err_ablated += (target24 - ablated24)**2
    return {"n_events": len(edges), "mean2": mu2, "var24": var24, "ablated24": ablated24,
            "empirical_variance_numerator": N * raw2 - raw*raw,
            "full_loss_sum_scaled576": err_full, "ablated_loss_sum_scaled576": err_ablated}


def shared(edges):
    """An event participates in one valid path at each of two distinct parity relays."""
    incoming, outgoing = defaultdict(set), defaultdict(set)
    for a, b in edges:
        outgoing[a].add(b)
        incoming[b].add(a)
    return any((a - b) % 2 and (incoming[a] - {b}) and (outgoing[b] - {a}) for a, b in edges)


def tau_b(rows, prediction):
    counts = dict(concordant=0, discordant=0, tie_prediction_only=0, tie_reference_only=0, tie_both=0)
    for a, b in combinations(rows, 2):
        dx = a[prediction] - b[prediction]
        dy = a["empirical_variance_numerator"] - b["empirical_variance_numerator"]
        key = ('tie_both' if dx == dy == 0 else 'tie_prediction_only' if dx == 0 else
               'tie_reference_only' if dy == 0 else 'concordant' if dx*dy > 0 else 'discordant')
        counts[key] += 1
    c, d = counts['concordant'], counts['discordant']
    denom = sqrt((c+d+counts['tie_prediction_only'])*(c+d+counts['tie_reference_only']))
    return dict(tau_b=(c-d)/denom if denom else None, **counts)


def summarize(rows):
    if not rows:
        return {"windows": 0, "permutations": 0}
    divisor = 576 * N * len(rows)
    less = sum(r["full_loss_sum_scaled576"] < r["ablated_loss_sum_scaled576"] for r in rows)
    equal = sum(r["full_loss_sum_scaled576"] == r["ablated_loss_sum_scaled576"] for r in rows)
    return dict(windows=len(rows), permutations=len(rows)*N,
                mse_full=sum(r["full_loss_sum_scaled576"] for r in rows) / divisor,
                mse_ablated=sum(r["ablated_loss_sum_scaled576"] for r in rows) / divisor,
                wins_ties_losses=[less, equal, len(rows)-less-equal],
                rank_full=tau_b(rows, 'var24'), rank_ablated=tau_b(rows, 'ablated24'))


def monte_carlo(edges, seed):
    stream = list(edges)
    rng = random.Random(seed)
    total = squares = 0
    for _ in range(N):
        rng.shuffle(stream)
        z = bm.ordered(stream, 'contrast')
        total += z
        squares += z*z
    return total / N, (N*squares - total*total)/(N*(N-1))


def profile(windows):
    # Compare the same mean and variance target, streaming results window by window.
    methods = {"endpoint": lambda e,s: bm.endpoint(e,'contrast')[:2],
               "explicit": lambda e,s: bm.explicit(e,'contrast'), "shuffle512": monte_carlo}
    profiles = {}
    for name, fn in methods.items():
        def run():
            for e, s in windows:
                fn(e,s)
        times = []
        for _ in range(3):
            start = time.perf_counter()
            run()
            times.append(time.perf_counter()-start)
        gc.collect()
        tracemalloc.start()
        try:
            run()
            peak = tracemalloc.get_traced_memory()[1]
        finally:
            tracemalloc.stop()
        profiles[name] = dict(seconds=times, median_s=statistics.median(times), peak_python_bytes=peak)
    return profiles


def main():
    file = Path('data/CollegeMsg.txt.gz')
    records, _ = bm.load(file)
    result = dict(source_sha256=hashlib.sha256(file.read_bytes()).hexdigest(), seed=SEED,
                  script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                  replicates=N, cap_per_stratum=CAP, affinity=sorted(os.sched_getaffinity(0)), widths={})
    for width in (60,3600,86400):
        buckets = defaultdict(list)
        for t,a,b in records:
            buckets[int(t // width)].append((a,b))
        eligible = {False:[], True:[]}
        for key, edges in buckets.items():
            # Informative contrast; require positive marginal variance in each parity group.
            va, vc, vo = [bm.endpoint(edges, q)[1] for q in ('all','contrast','odd')]
            ve = (va + vc) // 2 - vo
            assert (va + vc) % 2 == 0
            if vc > 0 and min(vo,ve) > 0:
                coupling = shared(edges)
                assert coupling == (va < vc)
                eligible[coupling].append(key)
        rng = random.Random(SEED + width)
        windows, rows = [], []
        for coupled in (False, True):
            keys = sorted(rng.sample(sorted(eligible[coupled]), min(CAP, len(eligible[coupled]))))
            for key in keys:
                seed = rng.getrandbits(64)
                edges = buckets[key]
                windows.append((edges,seed))
                rows.append(dict(bucket=key, shared=coupled, shuffle_seed=seed, **score_window(edges,seed)))
        result['widths'][width] = dict(eligible={"shared":len(eligible[True]), "disjoint":len(eligible[False])},
                                       shared=summarize([r for r in rows if r['shared']]),
                                       disjoint=summarize([r for r in rows if not r['shared']]),
                                       pooled=summarize(rows), records=rows, resources=profile(windows))
        print(width, "complete", flush=True)
    Path('results/candidate_check.json').write_text(json.dumps(result, indent=2)+'\n')


if __name__ == '__main__':
    main()
