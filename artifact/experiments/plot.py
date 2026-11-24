"""Rebuild the hourly all-relay variance figure from the archived results."""
import csv
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter

HERE = Path(__file__).resolve().parent
NAMES = {"CollegeMsg": "CollegeMsg", "EmailEU": "Email-EU",
         "BitcoinOTC": "Bitcoin OTC", "BitcoinAlpha": "Bitcoin Alpha"}


def load_ratios():
    with (HERE / "results/moments.csv").open(newline="", encoding="utf-8") as source:
        hourly = {r["dataset"]: r for r in csv.DictReader(source)
                  if r["width"] == "3600" and r["query"] == "all"}
    rows = []
    for name in NAMES:
        row = hourly[name]
        rows.append((NAMES[name], int(row["iid_var12"]) / int(row["var12"]),
                     int(row["diagonal_var12"]) / int(row["var12"])))
    transfer = json.loads((HERE / "results/sql.json").read_text(encoding="utf-8"))
    row = transfer["datasets"]["MathOverflowA2Q"]["moments"]["all"]
    rows.append(("MathOverflow A2Q\n(replication)", row["iid12"] / row["var12"],
                 row["diag12"] / row["var12"]))
    return rows


def main():
    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 9,
                         "svg.fonttype": "none", "svg.hashsalt": "hourly_variance"})
    rows = load_ratios()
    fig, ax = plt.subplots(figsize=(6.8, 3.15))
    fig.subplots_adjust(left=.235, right=.985, top=.84, bottom=.19)
    heights = [4.1, 3.2, 2.3, 1.4, .05]
    ax.axvline(1, color="#555963", linestyle=(0, (4, 3)), lw=.95, zorder=1)
    ax.axhline(.72, color="#c4c6c9", lw=.75)
    for i, (color, marker, label) in enumerate((
        ("#126480", "o", "Independent event pairs"),
        ("#98451d", "s", "Relay diagonal only"),
    )):
        values = [row[i + 1] for row in rows]
        ax.scatter(values, heights, s=27, c=color, marker=marker, label=label, zorder=3)
        for x, y in zip(values, heights):
            ax.annotate(f"{x:.3f}", (x, y), xytext=(6, 0), textcoords="offset points",
                        va="center", ha="left", color=color, fontsize=8)
    ax.set(yticks=heights, yticklabels=[row[0] for row in rows], ylim=(-.52, 4.57),
           xlim=(0, 1.39), xticks=[0, .25, .5, .75, 1, 1.25],
           xlabel="Estimated variance / exact variance")
    ax.xaxis.set_major_formatter(FuncFormatter(lambda x, _: f"{x:g}"))
    ax.legend(loc="lower left", bbox_to_anchor=(0, 1.025), ncol=2, frameon=False,
              handlelength=.95, columnspacing=1.5, borderaxespad=0)
    for name in ("left", "top", "right"):
        ax.spines[name].set_visible(False)
    ax.spines["bottom"].set_color("#707379")
    ax.tick_params(axis="y", length=0, pad=6)
    ax.tick_params(axis="x", color="#707379", length=3)
    target = HERE.parent / "figures/hourly_variance.svg"
    target.parent.mkdir(exist_ok=True)
    fig.savefig(target, metadata={"Date": None,
                                "Title": "Hourly variance ratios for all relays",
                                "Description": "The dashed reference line is exact agreement at 1."})
    plt.close(fig)


if __name__ == "__main__":
    main()
