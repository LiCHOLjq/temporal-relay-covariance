# Temporal relay covariance

Code and measurements for estimating the covariance of two-hop relay counts when timestamps conceal event order.

- [Original analysis](artifact/README.md) — download the public logs from Stanford SNAP, verify their checksums, and reproduce the baseline calculations.
- [Structural diagnostics](analysis/experiments/structure/README.md) — bucket widths and origins, timestamp gaps, native-order replay, and relay rankings.
- [Timing experiments](analysis/experiments/timing/README.md) — matched kernels, construction and query costs, scheduler measurements, and individual trials.
- [Figures](analysis/figures) — scripts and vector plots used in the manuscript.

The rights holder makes the code and derived statistics available for inspection and has not granted an open licence. Obtain the original event logs from their [source pages](artifact/DATA_SOURCES.md).
