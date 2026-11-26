# Pooled upper bound and hourly concentration

These calculations use the integer per-bucket results in the sibling `structure/results/` directory. Python 3.10 or later is sufficient. The script does not need network access or event-level data.

```sh
python analysis/experiments/diagnostics/diagnostics.py --out diagnostics-replay
```

- `bound_and_density.csv` records the exact-to-independent variance ratio, its pair-weighted ceiling, the percentage of that ceiling attained, and the buckets with the largest pair count and highest number of pairs per contact. The two bucket identifiers can differ. The exported integers reproduce ceiling utilization as `pooled_var12 / (sum_m_squared + 2*pooled_m)`.
- `hour_concentration.csv` records separate selections using all occupied hours or only positive-pair hours in the denominator. The sample size is the ceiling of 1% of that denominator. Both selections sort by decreasing eligible-pair count, resolving ties by increasing bucket identifier. Variance and pair **shares** use the whole-trace totals under either selection. The script checks the selected squared imbalance per pair by direct summation and by dividing the variance share by the pair share.
- `checks.json` gives the checksum of the per-bucket input and the counts of verified rows, and checks the intersection of the twelve Bitcoin Alpha partitions with the release-time analysis. Each partition has as many occupied buckets as there are distinct timestamps. Since each timestamp maps to a single bucket, these counts imply a one-to-one correspondence.

All calculations use unrounded integer counts or exact ratios until CSV display. The specific numerical findings refer to the supplied event logs and the stated bucket origins.

