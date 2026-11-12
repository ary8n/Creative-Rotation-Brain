#!/usr/bin/env python3
"""Paired-seed simulator evaluation for B1, B2, and clairvoyant."""

from __future__ import annotations

import argparse
import csv
import json
import math
import statistics
from pathlib import Path
from typing import Any

from simulator import (
    DAILY_BUDGET, FIRST_EVAL_DAY, LAST_EVAL_DAY, SimulatedAccount,
    clairvoyant_allocation, load_creatives, load_initial_history,
    uniform_allocation, windowed_greedy_allocation,
)
from policy import Policy

T_CRITICAL = {
    1: 12.706, 2: 4.303, 3: 3.182, 4: 2.776, 5: 2.571, 6: 2.447,
    7: 2.365, 8: 2.306, 9: 2.262, 10: 2.228, 11: 2.201, 12: 2.179,
    13: 2.160, 14: 2.145, 15: 2.131, 16: 2.120, 17: 2.110, 18: 2.101,
    19: 2.093, 20: 2.086, 21: 2.080, 22: 2.074, 23: 2.069, 24: 2.064,
    25: 2.060, 26: 2.056, 27: 2.052, 28: 2.048, 29: 2.045, 30: 2.042,
}
POLICIES = ("B1_uniform", "B2_windowed_greedy", "our_policy", "clairvoyant")
MEASURES = ("revenue", "spend", "impressions", "clicks", "purchases", "roas", "budget_utilization")


def interval(values: list[float]) -> dict[str, float | int]:
    n = len(values)
    mean = statistics.mean(values) if values else 0.0
    if n < 2:
        return {"n": n, "mean": mean, "ci95_low": mean, "ci95_high": mean}
    margin = T_CRITICAL.get(n - 1, 1.96) * statistics.stdev(values) / (n ** 0.5)
    return {"n": n, "mean": mean, "ci95_low": mean - margin, "ci95_high": mean + margin}


def aggregate(rows: list[dict[str, Any]]) -> dict[str, float]:
    result = {key: sum(float(row[key]) for row in rows) for key in
              ("budget", "spend", "impressions", "clicks", "purchases", "revenue")}
    result["roas"] = result["revenue"] / result["spend"] if result["spend"] else 0.0
    return result


def normalize_policy_shares(shares: dict[str, float], creatives: list[dict[str, str]],
                            daily_budget: float) -> dict[str, float]:
    """Apply the protocol's normalization before passing dollars to simulator."""
    known = {creative["creative_id"]: 0.0 for creative in creatives}
    for cid, value in shares.items():
        if cid not in known:
            continue
        amount = float(value)
        if not math.isfinite(amount) or amount < 0:
            raise ValueError("policy shares must be finite and nonnegative")
        known[cid] = amount
    total = sum(known.values())
    if total <= 0:
        return uniform_allocation(creatives, daily_budget)
    return {cid: value / total * daily_budget for cid, value in known.items()}


def run_episode(policy_name: str, seed: int, scenario: str,
                creatives: list[dict[str, str]], initial_history: list[dict[str, Any]],
                config: dict[str, Any]) -> tuple[dict[str, float], list[dict[str, float]]]:
    env = SimulatedAccount(seed, scenario, config=config, creatives=creatives,
                           initial_history=initial_history)
    policy = Policy(creatives, env.daily_budget, seed) if policy_name == "our_policy" else None
    all_rows: list[dict[str, Any]] = []
    daily: list[dict[str, float]] = []
    for day in range(FIRST_EVAL_DAY, LAST_EVAL_DAY + 1):
        history = env.policy_history(day)
        if policy_name == "B1_uniform":
            allocation = uniform_allocation(creatives, env.daily_budget)
        elif policy_name == "B2_windowed_greedy":
            allocation = windowed_greedy_allocation(creatives, history, day, env.daily_budget)
        elif policy_name == "our_policy":
            assert policy is not None
            shares = policy.allocate(day, history)
            allocation = normalize_policy_shares(shares, creatives, env.daily_budget)
        elif policy_name == "clairvoyant":
            allocation = clairvoyant_allocation(env, day)
        else:
            raise ValueError(f"unknown policy: {policy_name}")
        if abs(sum(allocation.values()) - env.daily_budget) > 1e-5:
            raise AssertionError(f"{policy_name} allocation did not sum to daily budget on day {day}")
        rows = env.step(day, allocation)
        all_rows.extend(rows)
        daily.append(aggregate(rows))
    totals = aggregate(all_rows)
    totals["budget_utilization"] = totals["spend"] / (DAILY_BUDGET * (LAST_EVAL_DAY - FIRST_EVAL_DAY + 1))
    return totals, daily


def build_report(seed_count: int = 20, seed_start: int = 1000,
                 scenarios: list[str] | None = None) -> dict[str, Any]:
    config_path = Path(__file__).resolve().parent / "config.json"
    config = json.loads(config_path.read_text(encoding="utf-8"))
    creatives, initial_history = load_creatives(), load_initial_history()
    scenario_names = scenarios or list(config["scenarios"])
    seed_values = list(range(seed_start, seed_start + seed_count))
    raw: dict[str, dict[str, list[dict[str, float]]]] = {
        scenario: {policy: [] for policy in POLICIES} for scenario in scenario_names}
    daily_raw: dict[str, dict[str, list[list[dict[str, float]]]]] = {
        scenario: {policy: [] for policy in POLICIES} for scenario in scenario_names}

    # Common seed values recreate the same latent world and random-number
    # streams for every benchmark, independent of execution order.
    for scenario in scenario_names:
        for seed in seed_values:
            for policy_name in POLICIES:
                totals, daily = run_episode(policy_name, seed, scenario, creatives, initial_history, config)
                raw[scenario][policy_name].append(totals)
                daily_raw[scenario][policy_name].append(daily)

    report: dict[str, Any] = {
        "method": "paired simulator runs; 95% two-sided t intervals across seed-level runs",
        "seed_count": seed_count, "seeds": seed_values,
        "policies": list(POLICIES), "scenarios": {},
        "normalized_capture": {},
        "normalized_capture_note": "(our policy mean revenue - B1 mean revenue) / (clairvoyant mean revenue - B1 mean revenue)",
    }
    summary_rows: list[dict[str, Any]] = []
    daily_rows: list[dict[str, Any]] = []
    for scenario in scenario_names:
        scenario_report: dict[str, Any] = {"policies": {}, "paired_differences": {}}
        for policy_name in POLICIES:
            episodes = raw[scenario][policy_name]
            per_seed = []
            for metric in ("revenue", "spend", "impressions", "clicks", "purchases"):
                per_seed.append((metric, interval([episode[metric] for episode in episodes])))
            roas = interval([episode["roas"] for episode in episodes])
            utilization = interval([episode["budget_utilization"] for episode in episodes])
            metrics = dict(per_seed)
            metrics["roas"] = roas
            metrics["budget_utilization"] = utilization
            scenario_report["policies"][policy_name] = metrics
            row: dict[str, Any] = {"scenario": scenario, "policy": policy_name, "seeds": seed_count}
            for metric in MEASURES:
                item = metrics[metric]
                row[f"{metric}_mean"] = item["mean"]
                row[f"{metric}_ci95_low"] = item["ci95_low"]
                row[f"{metric}_ci95_high"] = item["ci95_high"]
            row["normalized_capture"] = ""  # candidate policy does not exist yet
            summary_rows.append(row)

            for day_index in range(LAST_EVAL_DAY - FIRST_EVAL_DAY + 1):
                day_values = [daily_raw[scenario][policy_name][seed_index][day_index]
                              for seed_index in range(seed_count)]
                for metric in ("revenue", "spend", "impressions", "clicks", "purchases"):
                    summary = interval([v[metric] for v in day_values])
                    daily_rows.append({"scenario": scenario, "policy": policy_name,
                                       "day": FIRST_EVAL_DAY + day_index, "metric": metric,
                                       **summary})
                daily_roas = interval([v["revenue"] / v["spend"] if v["spend"] else 0.0
                                       for v in day_values])
                daily_rows.append({"scenario": scenario, "policy": policy_name,
                                   "day": FIRST_EVAL_DAY + day_index, "metric": "roas",
                                   **daily_roas})
                spend_summary = interval([v["spend"] / DAILY_BUDGET for v in day_values])
                daily_rows.append({"scenario": scenario, "policy": policy_name,
                                   "day": FIRST_EVAL_DAY + day_index,
                                   "metric": "budget_utilization", **spend_summary})

        for comparison_name, against in (("B2_minus_B1", "B2_windowed_greedy"),
                                         ("ours_minus_B1", "our_policy"),
                                         ("ours_minus_B2", "our_policy"),
                                         ("clairvoyant_minus_B1", "clairvoyant")):
            baseline = "B2_windowed_greedy" if comparison_name == "ours_minus_B2" else "B1_uniform"
            paired = [raw[scenario][against][i]["revenue"] - raw[scenario][baseline][i]["revenue"]
                      for i in range(seed_count)]
            scenario_report["paired_differences"][comparison_name] = interval(paired)
        b1_mean = scenario_report["policies"]["B1_uniform"]["revenue"]["mean"]
        oracle_mean = scenario_report["policies"]["clairvoyant"]["revenue"]["mean"]
        ours_mean = scenario_report["policies"]["our_policy"]["revenue"]["mean"]
        scenario_report["headroom_clairvoyant_over_B1"] = oracle_mean - b1_mean
        capture = (ours_mean - b1_mean) / (oracle_mean - b1_mean) if oracle_mean != b1_mean else None
        seed_capture = []
        for index in range(seed_count):
            denominator = raw[scenario]["clairvoyant"][index]["revenue"] - raw[scenario]["B1_uniform"][index]["revenue"]
            if abs(denominator) > 1e-9:
                seed_capture.append((raw[scenario]["our_policy"][index]["revenue"]
                                     - raw[scenario]["B1_uniform"][index]["revenue"]) / denominator)
        scenario_report["normalized_capture"] = {
            "ratio_of_means": capture,
            "seed_ratio_mean_and_95_ci": interval(seed_capture),
        }
        report["normalized_capture"][scenario] = scenario_report["normalized_capture"]
        for summary_row in summary_rows:
            if summary_row["scenario"] == scenario and summary_row["policy"] == "our_policy":
                summary_row["normalized_capture"] = capture if capture is not None else ""
        report["scenarios"][scenario] = scenario_report

    output_dir = Path(__file__).resolve().parent / "artifacts"
    output_dir.mkdir(exist_ok=True)
    (output_dir / "simulation_benchmarks.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    with (output_dir / "simulation_benchmarks.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(summary_rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(summary_rows)
    with (output_dir / "simulation_daily.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(daily_rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(daily_rows)
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seeds", type=int, default=20)
    parser.add_argument("--seed-start", type=int, default=1000)
    parser.add_argument("--scenarios", nargs="+", default=None,
                        help="scenario names from config.json (default: all)")
    args = parser.parse_args()
    if args.seeds < 2:
        parser.error("--seeds must be at least 2 to calculate uncertainty intervals")
    report = build_report(args.seeds, args.seed_start, args.scenarios)
    for scenario, item in report["scenarios"].items():
        print(f"[{scenario}]")
        for policy in POLICIES:
            metrics = item["policies"][policy]
            revenue = metrics["revenue"]
            roas = metrics["roas"]
            utilization = metrics["budget_utilization"]
            print(f"  {policy}: revenue ${revenue['mean']:,.0f} "
                  f"(95% CI ${revenue['ci95_low']:,.0f}–${revenue['ci95_high']:,.0f}); "
                  f"spend ${metrics['spend']['mean']:,.0f}; ROAS {roas['mean']:.3f}; "
                  f"budget use {utilization['mean']:.1%}")
        paired = item["paired_differences"]["B2_minus_B1"]
        print(f"  B2-B1 paired revenue delta: ${paired['mean']:,.0f} "
              f"(95% CI ${paired['ci95_low']:,.0f}–${paired['ci95_high']:,.0f})")
        for comparison in ("ours_minus_B1", "ours_minus_B2"):
            difference = item["paired_differences"][comparison]
            print(f"  {comparison} paired revenue delta: ${difference['mean']:,.0f} "
                  f"(95% CI ${difference['ci95_low']:,.0f}–${difference['ci95_high']:,.0f})")
        print(f"  normalized capture (ratio of means): "
              f"{item['normalized_capture']['ratio_of_means']:.3f}")


if __name__ == "__main__":
    main()
