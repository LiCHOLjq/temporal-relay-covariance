"""Check every covariance-matrix entry via pair-of-pairs probabilities.

Run alongside benchmark.py and permutation_oracle.py in the experiment directory.
"""
from collections import Counter, defaultdict
from fractions import Fraction
from itertools import combinations
from pathlib import Path
import gzip
import hashlib
import json
import os
import random

import benchmark
import permutation_oracle


def pair_cov(edges):
    # Each ordered candidate specifies two event IDs and its relay.
    paths = [(i, j, b) for i, (a, b) in enumerate(edges)
             for j, (c, d) in enumerate(edges) if b == c and len({a, b, d}) == 3]
    matrix = Counter()
    for i, j, u in paths:
        for k, l, v in paths:
            # 12 times the covariance, from uniform ranks of 2, 3, or 4 events.
            if (i, j) == (k, l):
                term = 3
            elif (i, j) == (l, k):
                term = -3
            elif i == k or j == l:
                term = 1
            elif i == l or j == k:
                term = -1
            else:
                term = 0
            matrix[u, v] += term
    return paths, matrix


def endpoint_matrix(edges):
    # Form the sparse matrix explicitly with relay basis vectors.
    multiplicity = Counter(edges)
    matrix = Counter()
    for (u, v), copies in multiplicity.items():
        succ = sum(n for (x, y), n in multiplicity.items() if x == v and y != u)
        pred = sum(n for (x, y), n in multiplicity.items() if y == u and x != v)
        matrix[v, v] += copies * (succ + succ * succ)
        matrix[u, u] += copies * pred * pred
        matrix[u, v] -= copies * pred * succ
        matrix[v, u] -= copies * pred * succ
    return matrix


def audit_real(path):
    bins = defaultdict(list)
    with gzip.open(path, 'rt') as stream:
        for line in stream:
            if line.startswith('#') or not line.strip():
                continue
            fields = line.replace(',', ' ').split()
            a, b = map(int, fields[:2])
            if a != b:
                bins[int(float(fields[-1]) // 3600)].append((a, b))
    # Include bins with at least one dependence between different relays.
    # This intentionally enriches for nonzero off-diagonal entries. It cannot
    # estimate how common coupling is across the original stream.
    eligible = []
    for hour, edges in bins.items():
        if 3 <= len(edges) <= 24:
            matrix = endpoint_matrix(edges)
            if any(a != b and value for (a, b), value in matrix.items()):
                eligible.append(hour)
    rng = random.Random(432991)
    chosen = sorted(rng.sample(sorted(eligible), min(32, len(eligible))))
    records = []
    for hour in chosen:
        edges = bins[hour]
        arcs, direct = pair_cov(edges)
        moment = endpoint_matrix(edges)
        assert direct == moment
        relays = sorted(set(p[2] for p in arcs))
        for q, mode in enumerate(benchmark.MODES):
            co = sum(permutation_oracle.weight(a)[q] * permutation_oracle.weight(b)[q] * n
                     for (a, b), n in direct.items())
            diag = sum(permutation_oracle.weight(a)[q] ** 2 * direct[a, a] for a in relays)
            mu2, var12, _, diag12 = benchmark.endpoint(edges, mode)
            assert mu2 == sum(permutation_oracle.weight(a)[q] for _, _, a in arcs)
            assert (var12, diag12) == (co, diag)
        off = [direct[a, b] for a, b in combinations(relays, 2)]
        records.append({"hour": hour, "m": len(edges), "arcs": len(arcs),
                        "matrix_entries": len(relays)**2, "offdiag_unordered": len(off),
                        "negative": sum(n < 0 for n in off), "positive": sum(n > 0 for n in off),
                        "minimum_offdiag_times12": min(off)})
    return {"eligible": len(eligible), "checked": len(chosen), "bins": records}


def main():
    cases = permutation_oracle.make()
    for row in cases:
        for i, mode in enumerate(benchmark.MODES):
            mu2, var12, _, _ = benchmark.endpoint(row["events"], mode)
            assert Fraction(mu2, 2) == Fraction(row["means"][i])
            assert Fraction(var12, 12) == Fraction(row["variances"][i])
    result = {"cpu_affinity": sorted(os.sched_getaffinity(0)),
              "exhaustive_bins": len(cases), "exhaustive_orders": sum(x["orders"] for x in cases),
              "query_modes": list(benchmark.MODES), "fixtures": cases,
              "script_hashes": {p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
                                for p in ("benchmark.py", "independent_check.py", "permutation_oracle.py")},
              "real": {name: audit_real(Path("data", name)) for name in sorted(benchmark.SOURCES.values())}}
    Path("independent_results.json").write_text(json.dumps(result, indent=1) + "\n")
    print({p: r["checked"] for p, r in result["real"].items()})


if __name__ == "__main__":
    main()
