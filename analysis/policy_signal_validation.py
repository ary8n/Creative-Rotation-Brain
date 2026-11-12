#!/usr/bin/env python3
"""Chronological holdout checks for metadata priors and an age decay term."""

from __future__ import annotations

import csv
import json
import math
import statistics
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read_inputs():
    with (ROOT / "data/creatives.csv").open(newline="", encoding="utf-8-sig") as f:
        creatives = list(csv.DictReader(f))
    with (ROOT / "data/daily_final.csv").open(newline="", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    for row in rows:
        for key in ("day", "spend", "revenue"):
            row[key] = float(row[key])
    return creatives, rows


def totals(rows):
    return sum(r["spend"] for r in rows), sum(r["revenue"] for r in rows)


def score_pairs(pairs):
    """pairs contain (prediction, observed rate, held-out spend)."""
    errors = [pred - observed for pred, observed, _ in pairs]
    total_spend = sum(weight for _, _, weight in pairs)
    return {
        "creatives": len(pairs),
        "mae": statistics.mean(abs(error) for error in errors),
        "rmse": math.sqrt(statistics.mean(error * error for error in errors)),
        "spend_weighted_rmse": math.sqrt(
            sum(error * error * weight for error, (_, _, weight) in zip(errors, pairs)) / total_spend
        ),
        "spend_weighted_mae": sum(abs(error) * weight for error, (_, _, weight) in zip(errors, pairs)) / total_spend,
        "heldout_spend": total_spend,
    }


def rate_for(rows, cid, first, last):
    matched = [r for r in rows if r["creative_id"] == cid and first <= r["day"] <= last]
    spend, revenue = totals(matched)
    return revenue, spend, revenue / spend if spend else None


def mean_age(launch_day: int, first: int, last: int) -> float:
    days = range(max(first, launch_day), last + 1)
    return statistics.mean(day - launch_day for day in days)


def validate():
    creatives, rows = read_inputs()
    meta = {c["creative_id"]: c for c in creatives}
    served = [c for c in creatives if c["launch_day"]]
    train = [r for r in rows if r["day"] <= 45]
    test = [r for r in rows if 46 <= r["day"] <= 60]
    prior_spend = 1000.0

    metadata_pairs = []
    for creative in served:
        cid = creative["creative_id"]
        # Hold out this creative's full history when building its metadata prior.
        other = [r for r in train if r["creative_id"] != cid]
        global_spend, global_revenue = totals(other)
        global_rate = global_revenue / global_spend
        component_rates = []
        for dimension in ("format", "hook_type"):
            group = [r for r in other if meta[r["creative_id"]][dimension] == creative[dimension]]
            group_spend, group_revenue = totals(group)
            group_rate = ((group_revenue + prior_spend * global_rate) /
                          (group_spend + prior_spend))
            component_rates.append(group_rate)
        # Very weak metadata weight: 5% log weight from each category.
        metadata_rate = global_rate * math.sqrt(
            component_rates[0] / global_rate * component_rates[1] / global_rate
        ) ** 0.1
        _, holdout_spend, observed = rate_for(rows, cid, 46, 60)
        if observed is not None:
            metadata_pairs.append((global_rate, metadata_rate, observed, holdout_spend))

    # Select a decay coefficient on days 31-45, then report untouched days
    # 46-60 performance. The target is ROAS prediction weighted by spend.
    early_global_spend, early_global_revenue = totals([r for r in rows if r["day"] <= 30])
    early_global = early_global_revenue / early_global_spend
    fit_rows = []
    for creative in served:
        cid = creative["creative_id"]
        launch = int(creative["launch_day"])
        if launch > 30:
            continue
        revenue, spend, _ = rate_for(rows, cid, 1, 30)
        prediction = (revenue + prior_spend * early_global) / (spend + prior_spend)
        _, validation_spend, observed = rate_for(rows, cid, 31, 45)
        if observed is None or validation_spend <= 0:
            continue
        age_delta = mean_age(launch, 31, 45) - mean_age(launch, 1, 30)
        fit_rows.append((prediction, observed, validation_spend, age_delta))
    candidate_lambdas = [i * 0.001 for i in range(31)]
    validation_scores = {}
    for decay in candidate_lambdas:
        validation_scores[decay] = math.sqrt(
            sum((pred * math.exp(-decay * age_delta) - observed) ** 2 * spend
                for pred, observed, spend, age_delta in fit_rows) /
            sum(spend for _, _, spend, _ in fit_rows)
        )
    selected_decay = min(candidate_lambdas, key=lambda decay: validation_scores[decay])

    train_global_spend, train_global_revenue = totals(train)
    train_global = train_global_revenue / train_global_spend
    age_pairs_no_decay = []
    age_pairs_decay = []
    for creative in served:
        cid = creative["creative_id"]
        launch = int(creative["launch_day"])
        revenue, spend, _ = rate_for(rows, cid, 1, 45)
        prediction = (revenue + prior_spend * train_global) / (spend + prior_spend)
        _, holdout_spend, observed = rate_for(rows, cid, 46, 60)
        if observed is None or holdout_spend <= 0:
            continue
        age_delta = mean_age(launch, 46, 60) - mean_age(launch, 1, 45)
        age_pairs_no_decay.append((prediction, observed, holdout_spend))
        age_pairs_decay.append((prediction * math.exp(-selected_decay * age_delta), observed, holdout_spend))

    baseline_pairs = [(global_rate, observed, spend)
                      for global_rate, _, observed, spend in metadata_pairs]
    metadata_pairs_for_score = [(metadata_rate, observed, spend)
                                for _, metadata_rate, observed, spend in metadata_pairs]
    report = {
        "split": {"metadata_train_days": [1, 45], "metadata_test_days": [46, 60],
                  "fatigue_fit_days": [1, 30], "fatigue_validation_days": [31, 45],
                  "fatigue_test_days": [46, 60]},
        "metadata": {"method": "leave-one-creative-out train prior; 0.1 log-weight on geometric mean of format and hook rates",
                     "global_prior": score_pairs(baseline_pairs),
                     "metadata_prior": score_pairs(metadata_pairs_for_score)},
        "fatigue": {"selected_log_decay_per_day": selected_decay,
                    "validation_spend_weighted_rmse": validation_scores[selected_decay],
                    "validation_no_decay_rmse": validation_scores[0.0],
                    "test_no_decay": score_pairs(age_pairs_no_decay),
                    "test_with_decay": score_pairs(age_pairs_decay),
                    "decision": "do not use age decay unless it improves spend-weighted held-out error"},
    }
    path = ROOT / "artifacts/policy_signal_validation.json"
    path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))
    return report


if __name__ == "__main__":
    validate()

