# Reproducing the two-hop relay covariance experiments

The scripts, measured outputs, numerical oracles and source hashes in this directory can be moved together. The original run used Linux, Python 3.12.3, SQLite 3.45.1 and a Xeon w9-3475X. All numerical experiments use the Python standard library. Rendering the figure requires Matplotlib (3.10.9 was used). The stored measurements are the reference run. Work in a copy when rerunning, since the programs write the original output filenames.

## Recover the inputs

From this directory run the following. The five original compressed inputs were copied directly from the experiment server into the sibling private cache. The command checks their SHA-256 digests and byte sizes before installing them under `experiments/data/`.

```sh
python3 verify_archive.py
python3 prepare_inputs.py --from-dir ../raw_input_cache
python3 prepare_inputs.py --check
```

With the artifact directory alone, `python3 prepare_inputs.py` downloads the same five archives from Stanford and verifies them. With a separate download cache, supply its path using `--from-dir`. [URLs, SHA-256 and compressed sizes](snap_sources.json) · [Data attribution and terms](DATA_SOURCES.md)

## Replay on Linux

Use Python with assertions enabled. The original runs pinned individual Python processes to logical CPUs. Running sequentially works on smaller machines. To pin a process, prepend `taskset -c N` with an allowed CPU index. Timing varies by hardware, affinity, Python build and concurrent load. The original primary, group and independent experiments could overlap on different CPUs.

```sh
cd experiments
python3 benchmark.py
python3 groups.py
python3 independent_check.py
python3 sql_check.py
python3 role_contrast.py
python3 candidate_check.py
python3 limits.py
python3 plot.py
```

| Program | Reference outputs | Checks or measurements |
| --- | --- | --- |
| benchmark.py | [moments.csv](experiments/results/moments.csv), [run.json](experiments/results/run.json), [shuffle.json](experiments/results/shuffle.json), [timings.json](experiments/results/timings.json), [synthetic.json](experiments/results/synthetic.json) | Every dataset by bucket width and query, native-order reference, exact small-bin permutation checks, pair-enumeration checks, randomization and timing. The variance columns in the CSV are multiplied by 12. |
| groups.py | [groups.json](experiments/results/groups.json) | Compiled covariance compared with direct and cached-term evaluation, including build time. |
| independent_check.py | [independent_results.json](experiments/independent_results.json) | Independent permutation oracle, explicit pair-of-pairs covariance on selected real bins and matrix checks. Imports permutation_oracle.py. |
| sql_check.py | [sql.json](experiments/results/sql.json) | SQLite queries, verification of matrix coefficients and a fifth network. |
| role_contrast.py | [role_contrast.json](experiments/results/role_contrast.json) | Groups defined by send and receive activity before the evaluation interval. |
| candidate_check.py | [candidate_check.json](experiments/results/candidate_check.json) | Shared-event and disjoint-event windows, parity contrasts, held-out shuffle scoring, rank ties and Python peak allocations. |
| limits.py | [limits.json](experiments/results/limits.json) | Constructed boundary cases with deterministic output. |
| plot.py | [hourly_variance.svg](figures/hourly_variance.svg) | Plots variance ratios from the main CSV and SQL transfer result. |

Integer moments, data hashes, seeds, sampled counts and membership of the selected windows provide repeatable correctness checks. The delivered raw timings and machine details document the measured run. The study design and later additions are described in the [primary protocol](experiments/PROTOCOL.md), [group-query protocol](experiments/GROUP_PROTOCOL.md) and [SQL transfer protocol](experiments/SQL_PROTOCOL.md).

See the [relocation replay report](replay_validation.json) for the compared outputs and the distinction between exact content and timing or affinity differences.
