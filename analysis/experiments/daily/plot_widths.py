"""Plot whole-trace paired timings for the hourly and daily partitions."""
import argparse
import csv
from pathlib import Path
from statistics import median

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import FixedLocator, NullLocator

HERE = Path(__file__).resolve().parent
TRACES = {
    "CollegeMsg": "CollegeMsg", "EmailEU": "Email EU",
    "BitcoinOTC": "Bitcoin OTC", "BitcoinAlpha": "Bitcoin Alpha",
    "MathOverflowA2Q": "MathOverflow",
}


def plot(source, output):
    observations = {}
    with source.open(newline="", encoding="utf-8") as stream:
        for row in csv.DictReader(stream):
            if row["scope"] == "full":
                key = (row["dataset"], int(row["width_s"]), int(row["trial"]))
                observations.setdefault(key, {})[row["method"]] = float(row["elapsed_ms"])

    fig, panels = plt.subplots(1, 2, figsize=(6.15, 2.5), sharey=True)
    fig.subplots_adjust(left=0.182, right=0.972, top=0.84, bottom=0.24, wspace=0.14)
    for ax, seconds, title in zip(panels, (3600, 86400), ("Hourly buckets", "Daily buckets")):
        ax.axvline(1, linestyle=(0, (4, 3)), color="#5d6870", linewidth=0.9)
        for y, name in enumerate(TRACES):
            trials = [observations[name, seconds, trial] for trial in range(1, 13)]
            enum = [t["enumerate"] for t in trials]
            end = [t["endpoint_exact"] for t in trials]
            ratios = [e / a for e, a in zip(enum, end)]
            # The vertical spread separates trials; only horizontal position encodes time.
            heights = [y - 0.25 + i / 22 for i in range(12)]
            ax.scatter(ratios, heights, s=9, facecolor="#a8bdc9", linewidth=0, zorder=2)
            ax.scatter(median(enum) / median(end), y, s=27, marker="D",
                       facecolor="#193f56", edgecolor="white", linewidth=0.5, zorder=3)
        ax.set_xscale("log", base=2)
        left, right = ax.get_xlim()
        ax.set_xlim(min(0.21, left), max(3.5, right))
        ax.set_title(title, fontsize=10, color="#24384a", loc="left", pad=9, fontweight="bold")
        ax.xaxis.set_major_locator(FixedLocator([0.25, 0.5, 1, 2]))
        ax.xaxis.set_minor_locator(NullLocator())
        ax.set_xticks([0.25, 0.5, 1, 2], ["0.25", "0.5", "1", "2"])
        ax.grid(axis="y", color="#e1e6e9", linewidth=0.5)
        ax.tick_params(axis="both", labelsize=8, colors="#24384a", length=2.5)
        ax.spines[["top", "right", "left"]].set_visible(False)
        ax.spines["bottom"].set_color("#9aa9b1")
    # A common scale lets readers compare the same workload across the two panels.
    limits = [ax.get_xlim() for ax in panels]
    for ax in panels:
        ax.set_xlim(min(pair[0] for pair in limits), max(pair[1] for pair in limits))
    panels[0].set_yticks(range(len(TRACES)), list(TRACES.values()))
    panels[0].set_ylim(len(TRACES) - 0.45, -0.55)
    fig.text(0.575, 0.058, "Enumeration time / endpoint time (log scale)",
             ha="center", fontsize=9, color="#24384a")
    output.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output, metadata={"CreationDate": None, "ModDate": None})
    plt.close(fig)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=HERE / "results/raw_timings.csv")
    parser.add_argument("--out", type=Path, default=HERE.parents[1] / "figures/width_timings.pdf")
    args = parser.parse_args()
    with plt.rc_context({"font.family": "DejaVu Sans", "pdf.fonttype": 42}):
        plot(args.source, args.out)
