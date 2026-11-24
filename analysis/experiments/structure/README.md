# Structural and timestamp diagnostics

Run from the extracted project root, which contains the sibling `artifact/` and `analysis/` directories. Python 3.10 or later is sufficient. The five original SNAP inputs are fetched through the archived project utility and verified independently by SHA-256. The script writes a fresh set of tables to the supplied output directory. For an offline replay, provide the directory containing the original compressed files with `--data`.

```sh
python artifact/prepare_inputs.py
python analysis/experiments/structure/structure.py --out structural-replay
```

The reference outputs in `results/` cover all five traces, 60-second, one-hour, and one-day bucket widths. The 36 original primary cells and the three hourly MathOverflow cells are checked against the archived moment numerators. The event files retain source precision, including decimal seconds in the Bitcoin OTC release. All public-file inputs are identified by checksum in `checks.json`. Data files and login details are excluded from this supplementary output.

| Output | Contents |
| --- | --- |
| `buckets.csv.gz` | One row per occupied, zero-phase bucket. Includes event count, eligible pairs, sum of squared role imbalances, sum of predecessor–successor products, and 12 times the all-relay variance. |
| `width_statistics.csv` | Fifteen primary-origin summaries, including positive and occupied buckets, largest pair count, pair-weighted mean, density, both structural averages, both variance ratios, and concentration totals. |
| `phase_statistics.csv` | The same summaries at four origins per width. Partitions use integer floor division of the timestamp minus the phase. The ordered list of bucket sizes is hashed for comparison, which fully determines a partition of the fixed sorted records up to bucket labels. |
| `timestamp_gaps.csv`, `gap_histogram.csv.gz` | Distinct release timestamps, exact positive consecutive gaps and frequencies, with and without self-contacts. The median is the ordinary sample median and the 95th percentile uses nearest rank. Changes in fractional precision are retained exactly. |
| `native_replay.csv` | Explicit hourly counts of eligible pairs whose first contact occurred earlier, later or simultaneously. Includes proportional differences from the coarse permutation mean and differences scaled by the conditional SD. |
| `query_moments.csv` | Zero-phase integer numerators for all-relay, odd-relay and odd-minus-even queries in all 45 cells. Divide `mean2` by two and each variance numerator by twelve. |
| `window_ranks.csv` | Analytical ranks on the same 94 sampled CollegeMsg windows as the initial study, including concordances, reversals, ties in each ranking and Kendall’s tau-b. Both variance scores are compared against fresh calculations for the sampled windows. |
| `shuffle_precision.csv` | Delete-one-replicate jackknife standard errors of the sample-to-exact variance ratios from the original 512 independent shuffle replicates per trace. |
| `checks.json`, `replay.json` | Input checksums, exact archive comparisons, execution provenance and cross-platform comparison of exported statistics. |

All ratios of approximate variance to exact variance are for all-relay weights unless the file gives another query explicitly. Densest-hour totals rank all occupied hours by eligible pair count, breaking ties by increasing hour index. The first ceil(H/100) buckets contribute to the reported concentration shares. Divide `top1_pairs` by `m` and `top1_var12` by `var12`. The original hourly criterion and original dataset split remain as recorded in `artifact/experiments/PROTOCOL.md`; phase shifts and structural diagnostics are secondary analyses.

