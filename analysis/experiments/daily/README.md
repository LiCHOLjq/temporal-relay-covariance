# Real-log daily single-query timings

This experiment compares equal-output kernels on five complete event logs at hourly and daily resolution. Four further workloads use individual days selected by pair count or pairs per event in CollegeMsg and Email EU. See [the measurement protocol](PROTOCOL.md) for the selection and timing rules.

## Reference run

All 14 workloads ran in one session on the designated experiment server. The worker was pinned to logical CPU 0 of an Intel Xeon w9-3475X. It used Linux 6.17.0-1033-oem and Python 3.12.3. Following one untimed warm-up for each method and workload, the two methods ran sequentially in alternating order over 12 paired trials. The kernel timer excludes data loading, bucket formation and comparisons of returned values. All inputs are checked against the original SHA-256 digests. There is no stochastic sampling or query generation in the daily benchmark.

## Reproduce

From the extracted package root, obtain the five original inputs with the data-preparation command in the top-level README. Then run

~~~sh
PYTHONHASHSEED=0 python3 analysis/experiments/daily/run_daily.py \
  --lib artifact/experiments --data artifact/experiments/data \
  --out analysis/experiments/daily/replay
python3 analysis/experiments/daily/summarize_daily.py \
  --source analysis/experiments/daily/replay \
  --out analysis/experiments/daily/replay_summary
~~~

Both programs use the Python standard library. The timing runner requires Linux CPU affinity, CPU topology information, and the scheduler counters in /proc. Its output directory must be empty. Use --cpu 0 to reproduce the recorded affinity on systems where logical CPU 0 is available. By default the program chooses an allowed logical CPU using a two-second core-idleness sample. For alternative input preparation, see [the data guide](../../../artifact/README.md).

To regenerate the summaries from the recorded run, execute the summarizer without arguments. It verifies all workload totals and selections against the independent per-bucket structure archive, checks the 12 trial indices and six first positions for each method, and writes the derived outputs. It also computes the amortization results from the original hourly timing study using unrounded medians, and compares the hourly enumeration measurements with their archived five-trial predecessors.

| File | Description |
| --- | --- |
| results/raw_timings.csv | All 336 elapsed-time measurements, with dataset, width, workload scope, paired trial and execution position. |
| results/workloads.csv | Events, pairs, scaled variance, density and number of occupied buckets. For individual days the bucket column is floor(source time / 86400). |
| results/environment.json | Hardware, software, worker affinity, session times, and checksums for code and inputs. |
| results/scheduler.csv | Aggregate wall time, worker CPU time, runnable delay and maximum sibling busy fraction for each of the 168 paired-trial intervals. |
| derived/daily_summary.csv | Unrounded median, inclusive interpolation quartiles, and ratios of medians for all workloads. |
| derived/amortization.csv | Hourly query-only and build-inclusive factors, compression, build shares, differential build times, and execution time per scanned item. |
| derived/checks.json | Numbers of verified workloads and timed records, monitored wall time, runnable delay and maximum observed sibling activity. |
