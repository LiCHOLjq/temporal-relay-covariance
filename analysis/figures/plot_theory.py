"""Render the explanatory examples by enumerating labelled event orders."""

from collections import Counter, defaultdict
from fractions import Fraction
from itertools import permutations
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, Rectangle

OUT = Path(__file__).resolve().parent
INK = "#24384A"
BLUE = "#286486"
ORANGE = "#AD592B"
RULE = "#C4D2DA"

plt.rcParams.update({
    "font.size": 9.5, "font.family": "DejaVu Sans", "pdf.fonttype": 42,
    "axes.labelcolor": INK, "text.color": INK, "xtick.color": INK, "ytick.color": INK,
})


def relay_scores(order, edges):
    scores = Counter()
    for rank, first in enumerate(order):
        u, v = edges[first]
        for second in order[rank + 1:]:
            source, target = edges[second]
            if source == v and target != u:
                scores[v] += 1
    return scores


def draw_network(ax, vertices, edges, highlighted=(), event_labels=False):
    for index, (u, v) in enumerate(edges):
        x0, y0 = vertices[u]
        x1, y1 = vertices[v]
        color = ORANGE if index in highlighted else BLUE
        ax.add_patch(FancyArrowPatch(
            (x0, y0), (x1, y1), arrowstyle="-|>", mutation_scale=11,
            linewidth=1.6, shrinkA=8.1, shrinkB=8.4, color=color,
        ))
        if event_labels:
            ax.text((x0+x1)/2, (y0+y1)/2+.10, f"$e_{index+1}$",
                    color=color, ha="center", va="bottom")
    for name, (x, y) in vertices.items():
        ax.scatter(x, y, s=210, color="white", edgecolor=INK, linewidths=1.1, zorder=3)
        ax.text(x, y, "$"+name+"$", va="center", ha="center", zorder=4, fontsize=10)


def panel(ax, heading):
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")
    ax.text(0, .96, heading, ha="left", va="top", fontsize=10.5, weight="bold")


def order_example():
    edges = [("a", "b"), ("b", "c"), ("c", "d")]
    groups = defaultdict(list)
    for order in permutations(range(3)):
        scores = relay_scores(order, edges)
        groups[scores["b"], scores["c"]].append("".join(str(i+1) for i in order))
    assert Fraction(len(groups[1, 1]), 6) - Fraction(1, 4) == Fraction(-1, 12)

    fig, (chain, table) = plt.subplots(1, 2, figsize=(6.30, 2.0))
    fig.subplots_adjust(left=.025, right=.989, top=.99, bottom=.035, wspace=.12)
    panel(chain, "(a)  Three contacts in one bucket")
    panel(table, "(b)  Joint counts over six orders")
    vertices = {v: (.065+i*.280, .61) for i, v in enumerate("abcd")}
    draw_network(chain, vertices, edges, highlighted=(1,), event_labels=True)
    chain.text(.04, .33, r"$X_b=1$  if  $e_1$ precedes $e_2$")
    chain.text(.04, .16, r"$X_c=1$  if  $e_2$ precedes $e_3$")

    x_start, cell_w, cell_h, y_start = .26, .35, .265, .11
    for c in (0, 1):
        table.text(x_start+(c+.5)*cell_w, .74, f"$X_c={c}$", ha="center")
    for b in (0, 1):
        y0 = y_start+(1-b)*cell_h
        table.text(x_start-.045, y0+cell_h/2, f"$X_b={b}$", va="center", ha="right")
        for c in (0, 1):
            x0 = x_start+c*cell_w
            orders = groups[b, c]
            table.add_patch(Rectangle(
                (x0, y0), cell_w, cell_h, edgecolor=RULE, linewidth=.8,
                facecolor="#EBF2F6" if b != c else "#FBF2EC",
            ))
            table.text(x0+cell_w/2, y0+.64*cell_h, f"{len(orders)}/6",
                       ha="center", va="center", fontweight="bold")
            table.text(x0+cell_w/2, y0+.23*cell_h, ", ".join(orders),
                       ha="center", va="center", fontsize=8)
    fig.savefig(OUT / "relay_orders.pdf", metadata={"CreationDate": None})
    plt.close(fig)


def extremes():
    fan = [("a", "b"), ("b", "c"), ("b", "d"), ("b", "e")]
    cycle = [("a", "b"), ("b", "c"), ("c", "a")]
    specs = [
        ("(a)  One shared incoming event", fan,
         {"a": (.16, .42), "b": (.45, .42), "c": (.79, .70),
          "d": (.79, .42), "e": (.79, .13)}, BLUE, Fraction(5, 4)),
        ("(b)  Directed cycle", cycle,
         {"a": (.47, .70), "b": (.72, .15), "c": (.22, .15)}, ORANGE, Fraction(1, 4)),
    ]
    fig, axs = plt.subplots(2, 2, figsize=(6.30, 3.15),
                            gridspec_kw={"height_ratios": [1.13, 1]})
    fig.subplots_adjust(left=.085, right=.985, top=.995, bottom=.17, hspace=.23, wspace=.31)
    for j, (heading, edges, vertices, color, variance) in enumerate(specs):
        graph, bars = axs[:, j]
        panel(graph, heading)
        draw_network(graph, vertices, edges)
        counts = Counter(sum(relay_scores(order, edges).values())
                         for order in permutations(range(len(edges))))
        size = sum(counts.values())
        probs = [Fraction(counts[i], size) for i in range(4)]
        mean = sum(i*p for i, p in enumerate(probs))
        assert mean == Fraction(3, 2)
        assert sum((i-mean)**2*p for i, p in enumerate(probs)) == variance
        bars.bar(range(4), list(map(float, probs)), color=color, width=.55, zorder=3)
        bars.set_xticks(range(4))
        bars.set_xlim(-.5, 3.5)
        bars.set_ylim(0, .59)
        bars.set_yticks([0, .25, .5], ["0", "¼", "½"])
        bars.set_xlabel("Total relay count, $S$", labelpad=1)
        if j == 0:
            bars.set_ylabel("Probability", labelpad=2)
        bars.spines[["top", "right"]].set_visible(False)
        for side in ("left", "bottom"):
            bars.spines[side].set_color(RULE)
        bars.tick_params(length=0, pad=3)
        bars.grid(axis="y", color=RULE, lw=.6, zorder=0)
    fig.savefig(OUT / "extremal_counts.pdf", metadata={"CreationDate": None})
    plt.close(fig)


if __name__ == "__main__":
    order_example()
    extremes()
