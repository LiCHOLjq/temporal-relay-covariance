# Sequential timing study

The reference measurements in results/ were made on the designated experiment server on 2026-11-24 using an isolated working directory. Run the commands below from the the project project root containing artifact/, raw_input_cache/, and analysis/.

## Reproduce the measurements

Use Linux with Python 3.10 or newer, SQLite 3.35 or newer (materialized CTEs), /proc and CPU topology support. The reference run used Python 3.12.3, SQLite 3.45.1 and Linux 6.17.0-1033-oem on an Intel Xeon w9-3475X. The timing driver uses the Python standard library and the original study kernels. It checks SHA-256 digests of all five compressed inputs before measurement. The original source URLs and preparation instructions are in [the artifact guide](../../../artifact/README.md). When using the downloader, substitute its populated artifact/experiments/data/ directory for raw_input_cache/.

~~~sh
PYTHONHASHSEED=0 python3 analysis/experiments/timing/run_timing.py \
  --lib artifact/experiments --data raw_input_cache \
  --out analysis/experiments/timing/replay
~~~

Supply a new empty output directory on each run. By default the driver samples CPU activity for two seconds, picks a core with low activity, and pins a single worker to an allowed logical CPU on that core. An optional --cpu N selects a particular allowed CPU. Each workload has one warm-up per method followed by 12 timed trials. The relative order of the methods is balanced over the 12 trials. No other revision experiment ran during the timing session.

## Workloads and estimators

- The four primary traces use the complete, unshifted hourly buckets. Python kernel times exclude common input parsing, sorting and bucket assignment. Each trial checks exact integer mean and variance numerators for every bucket. The full endpoint method additionally computes the two approximation numerators. The exact-only method retains the same generic weight calculation.
- Independently for each trace, a generator seeded with 5917 assigns weights in {-1, 0, 1} to sorted vertex identifiers for each of 64 queries. Both methods receive the same vectors. Each trial rebuilds each representation and records cumulative query evaluation times at every prefix from 1 through 64. Every prefix is charged one complete build. Prefix measurements share the build and the preceding queries. The 64 integer variance numerators must all agree between methods.
- The SQL study covers all five traces. Each trial creates a fresh in-memory database, builds the common indexed layout once and evaluates both plans in alternating order. Each SQL result is checked against a separately constructed Python matrix. Both plan rows carry the same layout time for that trial.
- The hub uses disjoint sets of k incoming and k outgoing spokes and the same three single-query kernels. The driver checks all exact outputs.
- Timing summaries use medians and interpolated inclusive quartiles. The speedup is the cache median divided by the matrix median. The band in the figure gives the interquartile range of the paired trial ratios. The sustained crossover is the smallest batch size with lower matrix time at that length and at every subsequent measured length through 64. The median curves define the point estimate. The same calculation on individual pairs of trials gives the reported range.
- Scheduler intervals span one workload and trial, including any output checks and bookkeeping inside that interval. Runnable wait is the scheduler delay for the pinned process. Sibling activity comes from Linux /proc/stat tick deltas. These diagnostics exclude input loading, warm-up and inter-phase setup.

## Rebuild summaries and the manuscript figure

Python and Matplotlib are needed for the figure (reference version 3.10.9). From the project root run

~~~sh
python3 analysis/experiments/timing/summarize_timing.py
~~~

The default input is the archived server run in results/. To summarize a new run add --source analysis/experiments/timing/replay. The command refreshes the derived products and analysis/figures/query_costs.pdf. Use a project copy to preserve the reference products while replaying. The final paper includes the LaTeX numeric rows inline. The separate figure-generation entry point analysis/figures/plot_results.py also uses this timing study.

The original five-trial single-query times and the three-trial 64-query build/evaluation split are read from artifact/experiments/results/timings.json and groups.json, respectively. The earlier CollegeMsg SQL common-layout observation was 64.767781 ms and the separately measured median degree-join time was 64.807405 ms in artifact/experiments/results/sql.json.

| File or directory | Contents |
| --- | --- |
| results/raw_timings.csv | 6,552 measured method/prefix rows in milliseconds. SQL preparation occurs once per trial and batch preparation once per method and trial. |
| results/environment.json | CPU, kernel and software versions, affinity, CPU siblings, UTC session limits, seed, and code and input checksums. |
| results/scheduler.csv | CPU activity and runnable wait for 204 monitored intervals. |
| results/sizes.json | Cached directed-type terms, active diagonals and nonzero unordered off-diagonal entries. |
| derived/ | Unrounded timing summaries, paired crossovers and per-query costs, original matrix-split records, scheduler summary, and publication table rows. |

