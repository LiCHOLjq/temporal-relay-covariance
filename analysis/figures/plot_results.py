"""Regenerate the two empirical figure PDFs from the archived experiment outputs.

Run from any directory with Python 3 and Matplotlib installed.
"""
import csv
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = Path(__file__).resolve().parent
RESULTS = HERE.parents[1] / "artifact" / "experiments" / "results"
INK, BLUE, ORANGE = "#24384a", "#286486", "#ad592b"
TRACES = {
    "CollegeMsg": ("CollegeMsg", BLUE, "o", "-"),
    "EmailEU": ("Email EU", ORANGE, "s", "--"),
    "BitcoinOTC": ("Bitcoin OTC", "#28796c", "^", "-."),
    "BitcoinAlpha": ("Bitcoin Alpha", "#71548a", "D", ":"),
}
META = {"CreationDate": None, "ModDate": None}
plt.rcParams.update({
    "font.family": "DejaVu Sans", "font.size": 9, "pdf.fonttype": 42,
    "axes.labelcolor": INK, "axes.edgecolor": INK, "text.color": INK,
    "xtick.color": INK, "ytick.color": INK, "axes.spines.right": False,
    "axes.spines.top": False, "axes.linewidth": 0.7,
    "xtick.major.width": 0.7, "ytick.major.width": 0.7,
    "legend.fontsize": 8, "legend.frameon": False, "legend.handlelength": 1.7,
    "lines.markersize": 4.7, "lines.linewidth": 1.45,
})


def read_json(filename):
    return json.loads((RESULTS / filename).read_text(encoding="utf-8"))


def trace_curve(axis, name, x, y):
    label, color, marker, line = TRACES[name]
    axis.plot(x, y, color=color, marker=marker, linestyle=line, label=label,
              markeredgewidth=0.65, markerfacecolor="white", zorder=3)


def reference(axis, orientation):
    line = axis.axhline if orientation == "horizontal" else axis.axvline
    line(1, color="#667884", lw=0.9, linestyle=(0, (4, 3)), zorder=1)


def title(axis, caption):
    axis.set_title(caption, loc="left", fontsize=10.5, fontweight="bold", pad=11)


def legend_below(axis):
    axis.legend(loc="upper center", bbox_to_anchor=(0.5, -0.29), ncol=2,
                borderaxespad=0, columnspacing=1.0, handletextpad=0.4)


def variance_figure():
    with (RESULTS / "moments.csv").open(newline="", encoding="utf-8") as stream:
        moments = {(r["dataset"], int(r["width"])): r for r in csv.DictReader(stream)
                   if r["query"] == "all"}
    labels = [values[0] for values in TRACES.values()] + ["MathOverflow"]
    hourly = [moments[name, 3600] for name in TRACES]
    transfer = read_json("sql.json")["datasets"]["MathOverflowA2Q"]["moments"]["all"]
    pair = [int(r["iid_var12"]) / int(r["var12"]) for r in hourly]
    diag = [int(r["diagonal_var12"]) / int(r["var12"]) for r in hourly]
    pair.append(transfer["iid12"] / transfer["var12"])
    diag.append(transfer["diag12"] / transfer["var12"])

    fig, (a, b) = plt.subplots(1, 2, figsize=(7.35, 3.2))
    fig.subplots_adjust(left=0.144, bottom=0.36, right=0.983, top=0.84, wspace=0.37)
    title(a, "(a) Hourly variance")
    y = [4.35, 3.35, 2.35, 1.35, 0.05]
    for pos, low, high in zip(y, pair, diag):
        a.hlines(pos, low, high, color="#cbd5db", lw=1.2, zorder=1)
    reference(a, "vertical")
    a.axhline(0.69, lw=0.65, color="#d4dce0")
    a.scatter(pair, y, marker="o", c=BLUE, s=26, zorder=3, label="Independent pairs")
    a.scatter(diag, y, marker="s", facecolors="white", edgecolors=ORANGE,
              linewidths=1.3, s=24, zorder=3, label="Relay diagonal")
    a.set(yticks=y, yticklabels=labels, ylim=(-0.48, 4.9), xlim=(0, 1.31),
          xticks=[0, 0.25, 0.50, 0.75, 1, 1.25], xlabel="Approximate / exact variance")
    a.spines["left"].set_visible(False)
    a.tick_params(axis="y", length=0)
    a.legend(loc="upper center", bbox_to_anchor=(0.48, -0.29), ncol=1,
             borderaxespad=0, handletextpad=0.3)

    title(b, "(b) Effect of bucket width")
    for name in TRACES:
        rows = [moments[name, width] for width in (60, 3600, 86400)]
        ratios = [int(r["iid_var12"]) / int(r["var12"]) for r in rows]
        trace_curve(b, name, [0, 1, 2], ratios)
    reference(b, "horizontal")
    b.set(xticks=[0, 1, 2], xticklabels=["1 min", "1 h", "1 d"],
          xlabel="Bucket width", ylabel="Pair / exact variance",
          ylim=(0, 1.07), yticks=[0, 0.25, 0.50, 0.75, 1.0], xlim=(-0.1, 2.1))
    legend_below(b)
    fig.savefig(HERE / "hourly_variance.pdf", metadata=META)
    plt.close(fig)


def cost_figure():
    """Regenerate the revised cost figure from the sequential timing run."""
    import runpy
    timing = HERE.parent / "experiments" / "timing"
    study = runpy.run_path(str(timing / "summarize_timing.py"))
    study["plot"](timing / "results")


if __name__ == "__main__":
    variance_figure()
    cost_figure()

