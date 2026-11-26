# Temporal relay covariance

Code and data summaries for computing the covariance of two-hop relay counts when timestamps conceal event order.

- [Original experiments and data sources](artifact/README.md)
- [Timestamp and relay statistics](analysis/experiments/structure/README.md)
- [Variance bounds and concentration](analysis/experiments/diagnostics/README.md)
- [Hourly query benchmarks](analysis/experiments/timing/README.md)
- [Hourly and daily comparisons](analysis/experiments/daily/README.md)
- [Figure scripts and plots](analysis/figures)

Run `python artifact/prepare_inputs.py` to download the five original logs from Stanford SNAP and verify their checksums. Source logs are distributed by their providers. The code and derived statistics are public for inspection. The rights holder has not granted an open licence.
