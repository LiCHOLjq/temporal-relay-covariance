"""Independent exact test vectors, using only direct counting and permutations."""
from fractions import Fraction
from itertools import permutations
from math import factorial
from pathlib import Path
import json
import random


def weight(relay):
    return 1, relay % 2, 2 * (relay % 2) - 1


def moments(events):
    n = len(events)
    count = factorial(n)
    sums = [0, 0, 0]
    squares = [0, 0, 0]
    for perm in permutations(range(n)):
        scores = [0, 0, 0]
        for idx, first in enumerate(perm):
            src, relay = events[first]
            for second in perm[idx + 1:]:
                mid, dst = events[second]
                if mid == relay and len({src, relay, dst}) == 3:
                    for k, w in enumerate(weight(mid)):
                        scores[k] += w
        for k, score in enumerate(scores):
            sums[k] += score
            squares[k] += score * score
    means = [Fraction(s, count) for s in sums]
    var = [Fraction(s, count) - m * m for s, m in zip(squares, means)]
    return {"means": [str(x) for x in means], "variances": [str(x) for x in var]}


def make():
    fixtures = {
        "empty": [], "single": [(1, 2)], "path": [(0, 1), (1, 2)],
        "reverse_only": [(1, 2), (2, 1)], "directed_triangle": [(1, 2), (2, 3), (3, 1)],
        "multiplicity": [(0, 1)] * 3 + [(1, 2)] * 3,
        "opposed_relays": [(3, 2), (2, 1), (1, 4), (2, 3), (1, 2), (4, 0)],
        "disjoint": [(1, 2), (2, 3), (4, 5), (5, 6)],
    }
    rng = random.Random(20261123)
    for i in range(48):
        nodes = rng.randint(3, 6)
        events = [tuple(rng.sample(range(nodes), 2)) for _ in range(rng.randint(2, 7))]
        fixtures[f"random-{i}"] = events
    out = []
    for name, events in fixtures.items():
        out.append({"name": name, "events": events, "orders": factorial(len(events)), **moments(events)})
    return out


if __name__ == "__main__":
    out = make()
    Path("oracle.json").write_text(json.dumps(out, indent=1) + "\n", encoding="utf-8")
    print(f"{len(out)} bins; {sum(case['orders'] for case in out):,} enumerated orders")
