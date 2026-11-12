#!/usr/bin/env python3
"""Reproduce the Creative Rotation Brain dataset audit using only stdlib."""

from __future__ import annotations

import csv
import json
import math
import statistics
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
OUT = ROOT / "artifacts"
DAILY_METRICS = ("budget", "spend", "impressions", "clicks", "purchases", "revenue")


def load_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open(newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        return list(reader.fieldnames or []), list(reader)


def numeric(rows: list[dict[str, str]], columns: tuple[str, ...]) -> None:
    for row in rows:
        for col in columns:
            if row[col] != "":
                row[col] = float(row[col])  # type: ignore[assignment]


def describe(values: list[float]) -> dict[str, float | int | None]:
    if not values:
        return {"n": 0, "sum": 0.0, "mean": None, "median": None, "min": None, "max": None}
    return {"n": len(values), "sum": sum(values), "mean": statistics.mean(values),
            "median": statistics.median(values), "min": min(values), "max": max(values)}


def write_csv(name: str, columns: list[str], rows: list[dict[str, object]]) -> None:
    with (OUT / name).open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=columns, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def svg_chart(name: str, title: str, labels: list[str], values: list[float], *,
              color: str = "#315b8a", y_label: str = "ROAS", width: int = 900,
              height: int = 440) -> None:
    """Write a simple dependency-free SVG bar chart."""
    left, right, top, bottom = 70, 24, 60, 100
    plot_w, plot_h = width - left - right, height - top - bottom
    vmax = max(values, default=1.0)
    ymax = max(1.0, math.ceil(vmax * 1.15 * 4) / 4)
    gap = 6
    bar_w = max(2, (plot_w - gap * max(0, len(values) - 1)) / max(1, len(values)))
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
           '<rect width="100%" height="100%" fill="white"/>',
           f'<text x="{width/2}" y="30" text-anchor="middle" font-family="sans-serif" font-size="20">{title}</text>',
           f'<text transform="translate(18 {top + plot_h/2}) rotate(-90)" text-anchor="middle" font-family="sans-serif" font-size="13">{y_label}</text>']
    for i in range(5):
        v = ymax * i / 4
        y = top + plot_h - plot_h * i / 4
        out.append(f'<line x1="{left}" y1="{y:.1f}" x2="{width-right}" y2="{y:.1f}" stroke="#ddd"/>')
        out.append(f'<text x="{left-10}" y="{y+4:.1f}" text-anchor="end" font-family="sans-serif" font-size="11">{v:.2f}</text>')
    for i, (label, value) in enumerate(zip(labels, values)):
        x = left + i * (bar_w + gap)
        h = max(0, value / ymax * plot_h)
        y = top + plot_h - h
        out.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{bar_w:.1f}" height="{h:.1f}" fill="{color}"/>')
        if len(labels) <= 50:
            out.append(f'<text transform="translate({x + bar_w/2:.1f} {top+plot_h+10}) rotate(55)" font-family="sans-serif" font-size="9">{label}</text>')
    out.append('</svg>')
    (OUT / name).write_text("\n".join(out) + "\n", encoding="utf-8")


def main() -> None:
    OUT.mkdir(exist_ok=True)
    schemas: dict[str, list[str]] = {}
    raw: dict[str, list[dict[str, str]]] = {}
    for name in ("creatives", "daily_reported", "daily_final", "competitor_launches"):
        schemas[name], raw[name] = load_csv(DATA / f"{name}.csv")
    creatives = raw["creatives"]
    reported, final = raw["daily_reported"], raw["daily_final"]
    competitors = raw["competitor_launches"]
    numeric(reported, DAILY_METRICS + ("day",))
    numeric(final, DAILY_METRICS + ("day",))
    numeric(competitors, ("day",))
    cmeta = {r["creative_id"]: r for r in creatives}
    rmap = {(int(r["day"]), r["creative_id"]): r for r in reported}
    fmap = {(int(r["day"]), r["creative_id"]): r for r in final}

    missing = {name: {col: sum(r[col] == "" for r in rows) for col in schemas[name]}
               for name, rows in raw.items()}
    daily_quality = {}
    for name, rows in (("daily_reported", reported), ("daily_final", final)):
        keys = [(int(r["day"]), r["creative_id"]) for r in rows]
        negative = {m: sum(float(r[m]) < 0 for r in rows) for m in DAILY_METRICS}
        daily_quality[name] = {
            "rows": len(rows), "duplicate_keys": len(keys) - len(set(keys)),
            "missing_by_column": missing[name], "negative_by_metric": negative,
            "creative_count": len({r["creative_id"] for r in rows}),
            "day_min": min(int(r["day"]) for r in rows), "day_max": max(int(r["day"]) for r in rows),
        }

    shared = set(rmap) & set(fmap)
    revisions = {}
    for metric in DAILY_METRICS:
        deltas = [float(fmap[k][metric]) - float(rmap[k][metric]) for k in shared]
        revisions[metric] = {"changed_rows": sum(d != 0 for d in deltas), "rows": len(deltas),
                             "delta_sum": sum(deltas), "absolute_delta_sum": sum(abs(d) for d in deltas),
                             "min_delta": min(deltas), "max_delta": max(deltas)}
    revision_windows = []
    for start, end in ((1, 7), (8, 14), (15, 30), (31, 45), (46, 60)):
        keys = [k for k in shared if start <= k[0] <= end]
        revision_windows.append({
            "start_day": start, "end_day": end, "rows": len(keys),
            "purchase_changed_rows": sum(float(fmap[k]["purchases"]) != float(rmap[k]["purchases"]) for k in keys),
            "purchase_delta": sum(float(fmap[k]["purchases"]) - float(rmap[k]["purchases"]) for k in keys),
            "revenue_changed_rows": sum(float(fmap[k]["revenue"]) != float(rmap[k]["revenue"]) for k in keys),
            "revenue_delta": sum(float(fmap[k]["revenue"]) - float(rmap[k]["revenue"]) for k in keys),
        })

    per_creative: dict[str, dict[str, float | int | str]] = {}
    grouped: dict[str, dict[str, list[dict[str, object]]]] = {
        "format": defaultdict(list), "hook_type": defaultdict(list)}
    by_creative_rows: dict[str, list[dict[str, object]]] = defaultdict(list)
    for row in final:
        cid = str(row["creative_id"])
        by_creative_rows[cid].append(row)
        for dim in grouped:
            grouped[dim][str(cmeta[cid][dim])].append(row)
    creative_rows = []
    for cid, rows in sorted(by_creative_rows.items()):
        spend = sum(float(r["spend"]) for r in rows)
        revenue = sum(float(r["revenue"]) for r in rows)
        purchases = sum(float(r["purchases"]) for r in rows)
        roas = revenue / spend if spend else None
        launch = int(cmeta[cid]["launch_day"])
        per_creative[cid] = {"launch_day": launch, "format": cmeta[cid]["format"],
                             "hook_type": cmeta[cid]["hook_type"], "rows": len(rows),
                             "spend": spend, "revenue": revenue, "purchases": purchases, "roas": roas}
        creative_rows.append({"creative_id": cid, "launch_day": launch,
                              "format": cmeta[cid]["format"], "hook_type": cmeta[cid]["hook_type"],
                              "rows": len(rows), "spend": round(spend, 2), "revenue": round(revenue, 2),
                              "purchases": int(purchases), "roas": round(roas, 6) if roas is not None else ""})
    roases = sorted(float(v["roas"]) for v in per_creative.values() if v["roas"] is not None)
    quantile = lambda p: roases[max(0, math.ceil(p * len(roases)) - 1)]

    group_summaries = {}
    group_rows = []
    for dim, groups in grouped.items():
        group_summaries[dim] = {}
        for key, rows in sorted(groups.items()):
            spend = sum(float(r["spend"]) for r in rows)
            revenue = sum(float(r["revenue"]) for r in rows)
            impressions = sum(float(r["impressions"]) for r in rows)
            clicks = sum(float(r["clicks"]) for r in rows)
            purchases = sum(float(r["purchases"]) for r in rows)
            ncreative = len({str(r["creative_id"]) for r in rows})
            values = {"rows": len(rows), "creatives": ncreative, "spend": spend, "revenue": revenue,
                      "roas": revenue / spend if spend else None,
                      "ctr": clicks / impressions if impressions else None,
                      "purchase_per_click": purchases / clicks if clicks else None}
            group_summaries[dim][key] = values
            group_rows.append({"dimension": dim, "value": key, "rows": len(rows), "creatives": ncreative,
                               "spend": round(spend, 2), "revenue": round(revenue, 2),
                               "roas": round(revenue / spend, 6) if spend else "",
                               "ctr": round(clicks / impressions, 6) if impressions else "",
                               "purchases_per_click": round(purchases / clicks, 6) if clicks else ""})

    daily = defaultdict(lambda: {"budget": 0.0, "spend": 0.0, "revenue": 0.0, "rows": 0})
    for row in final:
        d = int(row["day"])
        for metric in ("budget", "spend", "revenue"):
            daily[d][metric] += float(row[metric])
        daily[d]["rows"] += 1
    daily_rows = []
    for day in sorted(daily):
        vals = daily[day]
        daily_rows.append({"day": day, "rows": vals["rows"], "budget": round(vals["budget"], 2),
                           "spend": round(vals["spend"], 2), "revenue": round(vals["revenue"], 2),
                           "roas": round(vals["revenue"] / vals["spend"], 6) if vals["spend"] else ""})
    weekly_rows = []
    for start in range(1, 61, 7):
        rows = [r for r in final if start <= int(r["day"]) < start + 7]
        spend = sum(float(r["spend"]) for r in rows)
        revenue = sum(float(r["revenue"]) for r in rows)
        impressions = sum(float(r["impressions"]) for r in rows)
        clicks = sum(float(r["clicks"]) for r in rows)
        purchases = sum(float(r["purchases"]) for r in rows)
        end = min(start + 6, 60)
        weekly_rows.append({"start_day": start, "end_day": end, "rows": len(rows), "spend": round(spend, 2),
                            "revenue": round(revenue, 2), "roas": round(revenue / spend, 6) if spend else "",
                            "ctr": round(clicks / impressions, 6) if impressions else "",
                            "purchases_per_click": round(purchases / clicks, 6) if clicks else ""})

    age_bins = []
    for lo, hi in ((0, 2), (0, 6), (7, 13), (14, 27), (28, 60)):
        rows = [r for cid, crs in by_creative_rows.items() for r in crs
                if lo <= int(r["day"]) - int(cmeta[cid]["launch_day"]) <= hi]
        spend = sum(float(r["spend"]) for r in rows)
        revenue = sum(float(r["revenue"]) for r in rows)
        age_bins.append({"age_start": lo, "age_end": hi, "rows": len(rows),
                         "creatives": len({str(r["creative_id"]) for r in rows}), "spend": spend,
                         "revenue": revenue, "roas": revenue / spend if spend else None})
    first7 = []
    for cid, crs in sorted(by_creative_rows.items()):
        launch = int(cmeta[cid]["launch_day"])
        rows = [r for r in crs if 0 <= int(r["day"]) - launch < 7]
        spend = sum(float(r["spend"]) for r in rows)
        revenue = sum(float(r["revenue"]) for r in rows)
        first7.append({"creative_id": cid, "launch_day": launch, "rows": len(rows), "spend": round(spend, 2),
                       "revenue": round(revenue, 2), "roas": round(revenue / spend, 6) if spend else ""})

    served = [c for c in creatives if c["launch_day"] != ""]
    unserved = [c for c in creatives if c["launch_day"] == ""]
    own_launch_days = {int(c["launch_day"]) for c in served}
    competitor_days = {int(r["day"]) for r in competitors}
    summary = {
        "files": {name: {"rows": len(raw[name]), "columns": schemas[name]} for name in raw},
        "missing_values": missing,
        "daily_quality": daily_quality,
        "reported_vs_final": {"shared_keys": len(shared), "reported_only_keys": len(set(rmap) - set(fmap)),
                              "final_only_keys": len(set(fmap) - set(rmap)), "by_metric": revisions,
                              "reported_outcome_totals": {m: sum(float(r[m]) for r in reported) for m in ("purchases", "revenue")},
                              "final_outcome_totals": {m: sum(float(r[m]) for r in final) for m in ("purchases", "revenue")},
                              "windows": revision_windows},
        "creatives": {"total": len(creatives), "served": len(served), "unserved": len(unserved),
                      "unserved_ids": [c["creative_id"] for c in unserved],
                      "formats": dict(Counter(c["format"] for c in creatives)),
                      "hook_types": dict(Counter(c["hook_type"] for c in creatives)),
                      "served_launch_day_min": min(int(c["launch_day"]) for c in served),
                      "served_launch_day_max": max(int(c["launch_day"]) for c in served)},
        "final_totals": {m: describe([float(r[m]) for r in final]) for m in DAILY_METRICS},
        "spend_vs_budget": {"budget_total": sum(float(r["budget"]) for r in final),
                            "spend_total": sum(float(r["spend"]) for r in final),
                            "spend_to_budget": sum(float(r["spend"]) for r in final) / sum(float(r["budget"]) for r in final),
                            "rows_under_budget": sum(float(r["spend"]) < float(r["budget"]) for r in final),
                            "rows_over_budget": sum(float(r["spend"]) > float(r["budget"]) for r in final),
                            "rows_equal_budget": sum(float(r["spend"]) == float(r["budget"]) for r in final),
                            "zero_spend_rows": sum(float(r["spend"]) == 0 for r in final),
                            "daily_budget_distribution": describe([v["budget"] for v in daily.values()]),
                            "daily_spend_distribution": describe([v["spend"] for v in daily.values()])},
        "creative_roas": {"n": len(roases), "mean": statistics.mean(roases), "median": statistics.median(roases),
                          "p25_nearest_rank": quantile(0.25), "p75_nearest_rank": quantile(0.75),
                          "min": min(roases), "max": max(roases), "above_1": sum(x > 1 for x in roases),
                          "above_1_5": sum(x > 1.5 for x in roases), "above_2": sum(x > 2 for x in roases)},
        "by_format_and_hook": group_summaries,
        "temporal": {"weekly": weekly_rows, "daily": daily_rows, "age_bins": age_bins,
                     "first_10_days": {"days": 10, "spend": sum(float(r["spend"]) for r in final if int(r["day"]) <= 10),
                                       "revenue": sum(float(r["revenue"]) for r in final if int(r["day"]) <= 10)},
                     "last_10_days": {"days": 10, "spend": sum(float(r["spend"]) for r in final if int(r["day"]) >= 51),
                                      "revenue": sum(float(r["revenue"]) for r in final if int(r["day"]) >= 51)}},
        "first_seven_days_by_creative": first7,
        "competitors": {"launches": len(competitors), "by_competitor": dict(Counter(r["competitor"] for r in competitors)),
                        "by_platform": dict(Counter(r["platform"] for r in competitors)),
                        "by_format": dict(Counter(r["format"] for r in competitors)),
                        "by_hook_type": dict(Counter(r["hook_type"] for r in competitors)),
                        "own_unique_launch_days": len(own_launch_days),
                        "own_launch_days_same_day_as_competitor": sum(d in competitor_days for d in own_launch_days),
                        "own_launch_days_within_3_days_of_competitor": sum(any(abs(d-x) <= 3 for x in competitor_days) for d in own_launch_days)},
        "data_quality_relations": {"clicks_gt_impressions": sum(float(r["clicks"]) > float(r["impressions"]) for r in final),
                                   "purchases_gt_clicks": sum(float(r["purchases"]) > float(r["clicks"]) for r in final),
                                   "positive_revenue_zero_purchases": sum(float(r["revenue"]) > 0 and float(r["purchases"]) == 0 for r in final),
                                   "positive_purchases_zero_revenue": sum(float(r["purchases"]) > 0 and float(r["revenue"]) == 0 for r in final)},
    }
    (OUT / "audit_summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    write_csv("creative_performance.csv", ["creative_id", "launch_day", "format", "hook_type", "rows", "spend", "revenue", "purchases", "roas"], creative_rows)
    write_csv("group_performance.csv", ["dimension", "value", "rows", "creatives", "spend", "revenue", "roas", "ctr", "purchases_per_click"], group_rows)
    write_csv("weekly_performance.csv", ["start_day", "end_day", "rows", "spend", "revenue", "roas", "ctr", "purchases_per_click"], weekly_rows)
    write_csv("creative_age_performance.csv", ["age_start", "age_end", "rows", "creatives", "spend", "revenue", "roas"],
              [{**r, "spend": round(float(r["spend"]), 2), "revenue": round(float(r["revenue"]), 2), "roas": round(float(r["roas"]), 6)} for r in age_bins])
    write_csv("creative_first7.csv", ["creative_id", "launch_day", "rows", "spend", "revenue", "roas"], first7)
    sorted_creatives = sorted(creative_rows, key=lambda r: float(r["roas"]))
    svg_chart("creative_roas.svg", "Creative cumulative ROAS (final export)", [str(r["creative_id"]) for r in sorted_creatives], [float(r["roas"]) for r in sorted_creatives], width=1200, height=520)
    svg_chart("format_roas.svg", "Observed ROAS by format", list(group_summaries["format"]), [float(v["roas"]) for v in group_summaries["format"].values()], color="#4f7e58")
    svg_chart("hook_roas.svg", "Observed ROAS by hook type", list(group_summaries["hook_type"]), [float(v["roas"]) for v in group_summaries["hook_type"].values()], color="#9a6139")
    svg_chart("weekly_roas.svg", "Observed ROAS over time (final export)", [f'{r["start_day"]}-{r["end_day"]}' for r in weekly_rows], [float(r["roas"]) for r in weekly_rows], color="#8b4d77")
    print(f"Wrote {len(list(OUT.iterdir()))} artifacts to {OUT.relative_to(ROOT)}")
    print(f"Rows: reported={len(reported)}, final={len(final)}, creatives={len(creatives)}, competitors={len(competitors)}")
    print(f"Revisions: purchases={revisions['purchases']['changed_rows']} rows / {revisions['purchases']['delta_sum']:.0f}; "
          f"revenue={revisions['revenue']['changed_rows']} rows / ${revisions['revenue']['delta_sum']:.2f}")
    print(f"Creative ROAS: n={len(roases)}, mean={statistics.mean(roases):.3f}, median={statistics.median(roases):.3f}, "
          f"range={min(roases):.3f}-{max(roases):.3f}")
    print(f"Spend/budget: ${summary['spend_vs_budget']['spend_total']:.2f}/${summary['spend_vs_budget']['budget_total']:.2f} "
          f"({summary['spend_vs_budget']['spend_to_budget']:.3%}); unserved creatives={len(unserved)}")


if __name__ == "__main__":
    main()
