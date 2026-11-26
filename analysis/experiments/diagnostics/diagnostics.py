"""Evaluate pooled bounds, density and concentration from the archived integer bucket data."""
import argparse
import csv
import gzip
import hashlib
import itertools
import json
from fractions import Fraction
from pathlib import Path

HERE = Path(__file__).resolve().parent
DEFAULT_INPUT = HERE.parent / "structure" / "results"


def save_csv(path, rows):
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def row_totals(rows):
    m = sum(row["m"] for row in rows)
    var12 = sum(row["var12"] for row in rows)
    sq = sum(row["sum_role_square"] for row in rows)
    assert var12 == m + sq
    return m, var12, sq


def concentration(dataset, rows):
    positive = [r for r in rows if r["m"] > 0]
    ranked = sorted(positive, key=lambda r: (-r["m"], r["bucket"]))
    total_m, total_var12, total_sq = row_totals(rows)
    summaries = []
    for label, denominator in (("occupied", len(rows)), ("positive", len(positive))):
        count = (denominator + 99) // 100
        # Every selected hour at hourly resolution has a positive pair count in these five logs.
        assert count <= len(ranked)
        m, var12, sq = row_totals(ranked[:count])
        pair_share = Fraction(m, total_m)
        variance_share = Fraction(var12, total_var12)
        q = Fraction(total_sq, total_m)
        q_selected = Fraction(sq, m)
        assert q_selected == (variance_share / pair_share) * (1 + q) - 1
        summaries.append(dict(dataset=dataset,selection_denominator=label,H=len(rows),
                              H_positive=len(positive),selected=count,
                              pct_positive=100 * float(Fraction(count, len(positive))),
                              selected_m=m,selected_var12=var12,selected_sq=sq,
                              pooled_m=total_m,pooled_var12=total_var12,pooled_sq=total_sq,
                              pct_pairs=100 * float(pair_share),pct_variance=100 * float(variance_share),
                              q_all=float(q),q_selected=float(q_selected),q_multiple=float(q_selected/q)))
    return summaries


def summarize(dataset, width, rows, archived):
    m, var12, _ = row_totals(rows)
    sum_m_squared = sum(r["m"] ** 2 for r in rows)
    assert m == int(archived["m"])
    assert var12 == int(archived["var12"])
    assert sum_m_squared == int(archived["sum_m_squared"])
    assert all(3*r["m"] <= r["contacts"]**2 for r in rows)
    # With fixed timestamps, prefer the earliest bucket if several share the maximum density.
    densest = max(rows, key=lambda r: (Fraction(r["m"], r["contacts"]), -r["bucket"]))
    most_pairs = max(rows, key=lambda r: (r["m"], -r["bucket"]))
    exact_ratio = Fraction(var12, 3*m)
    upper = Fraction(sum_m_squared + 2*m, 3*m)
    utilization = exact_ratio / upper
    assert 0 < utilization <= 1
    return dict(dataset=dataset,width_s=width,pooled_m=m,pooled_var12=var12,
                sum_m_squared=sum_m_squared,exact_to_pair=float(exact_ratio),pooled_ceiling=float(upper),
                ceiling_utilization_pct=100*float(utilization),max_pairs=most_pairs["m"],
                max_pairs_contacts=most_pairs["contacts"],max_pairs_bucket=most_pairs["bucket"],
                max_density_pairs=densest["m"],max_density_contacts=densest["contacts"],
                max_density_bucket=densest["bucket"],max_density=densest["m"]/densest["contacts"])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT, help="Archived structure/results directory")
    parser.add_argument("--out", type=Path, default=HERE / "results")
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    expected = {}
    with (args.input / "width_statistics.csv").open(encoding="utf-8") as stream:
        for r in csv.DictReader(stream):
            expected[r["dataset"], int(r["width_s"])] = r
    bounds, subsets = [], []
    path = args.input / "buckets.csv.gz"
    with gzip.open(path, "rt", encoding="utf-8", newline="") as stream:
        reader = csv.DictReader(stream)
        for (dataset, width), group in itertools.groupby(reader, key=lambda r:(r["dataset"], int(r["width_s"]))):
            rows = [{k: int(v) for k,v in r.items() if k not in ("dataset","width_s")} for r in group]
            bounds.append(summarize(dataset, width, rows, expected[dataset,width]))
            if width == 3600:
                subsets.extend(concentration(dataset, rows))
    assert len(bounds) == len(expected) == 15 and len(subsets) == 10
    with (args.input / "phase_statistics.csv").open(encoding="utf-8") as stream:
        alpha = [r for r in csv.DictReader(stream) if r["dataset"] == "BitcoinAlpha"]
    with (args.input / "timestamp_gaps.csv").open(encoding="utf-8") as stream:
        alpha_gaps = next(r for r in csv.DictReader(stream) if r["dataset"] == "BitcoinAlpha" and r["scope"] == "analysis")
    assert len(alpha) == 12 and {int(r["occupied"]) for r in alpha} == {int(alpha_gaps["distinct_times"])}
    assert len({r["partition_sha256"] for r in alpha}) == 1
    save_csv(args.out / "bound_and_density.csv", bounds)
    save_csv(args.out / "hour_concentration.csv", subsets)
    provenance = dict(input_sha256=hashlib.sha256(path.read_bytes()).hexdigest(), checked_width_cells=len(bounds),
                      hourly_subset_rows=len(subsets),alpha_same_partition_cells=len(alpha),
                      alpha_distinct_times=int(alpha_gaps["distinct_times"]))
    (args.out / "checks.json").write_text(json.dumps(provenance,indent=2)+"\n",encoding="utf-8")


if __name__ == "__main__":
    main()

