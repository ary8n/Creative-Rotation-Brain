"""Conservative contextual allocation policy using protocol inputs only."""

from __future__ import annotations

import math
from collections import defaultdict
from typing import Any


class Policy:
    """Estimate creative return from history, then allocate with bounded UCB.

    No simulator modules, files, network, or ground-truth parameters are read.
    The policy is stateless between calls: repeated inputs produce the same
    split, and skipped/repeated days do not corrupt internal state.
    """

    # Policy choices, not fitted simulator parameters.
    _META_LOG_WEIGHT = 0.10
    _META_GROUP_PRIOR_SPEND = 1000.0
    _CREATIVE_PRIOR_SPEND = 800.0
    _RECENT_PRIOR_SPEND = 250.0
    _EXPLORATION_BONUS = 0.15
    _UNCERTAINTY_PRIOR_SPEND = 600.0
    _SERVED_FLOOR = 2.0
    _COLD_START_FLOOR = 8.0
    _MAX_ALLOCATION_FRACTION = 0.20
    _SCORE_POWER = 7.0

    def __init__(self, creatives: list[dict], daily_budget: float, seed: int):
        self.daily_budget = float(daily_budget)
        if not math.isfinite(self.daily_budget) or self.daily_budget <= 0:
            raise ValueError("daily_budget must be a positive finite number")
        self.seed = int(seed)
        self.creatives = [dict(c) for c in creatives]
        self.ids = [str(c["creative_id"]) for c in self.creatives if c.get("creative_id")]
        if not self.ids or len(self.ids) != len(set(self.ids)):
            raise ValueError("creatives must have unique creative_id values")
        self.by_id = {str(c["creative_id"]): c for c in self.creatives}

    @staticmethod
    def _number(value: Any) -> float:
        try:
            result = float(value)
        except (TypeError, ValueError, OverflowError):
            return 0.0
        return result if math.isfinite(result) and result >= 0 else 0.0

    @staticmethod
    def _row_day(row: dict) -> int | None:
        try:
            value = float(row.get("day"))
        except (TypeError, ValueError, OverflowError):
            return None
        if not math.isfinite(value) or value < 1 or not value.is_integer():
            return None
        return int(value)

    def _clean_history(self, day: int, history: list[dict]) -> list[dict[str, Any]]:
        """Ignore malformed, unknown, duplicate, and future rows safely."""
        if not isinstance(history, list):
            return []
        latest: dict[tuple[int, str], dict[str, Any]] = {}
        for raw in history:
            if not isinstance(raw, dict):
                continue
            cid = raw.get("creative_id")
            if not isinstance(cid, str) or cid not in self.by_id:
                continue
            row_day = self._row_day(raw)
            if row_day is None or row_day >= day:
                continue
            item: dict[str, Any] = {"day": row_day, "creative_id": cid}
            for key in ("budget", "spend", "impressions", "clicks", "purchases", "revenue"):
                item[key] = self._number(raw.get(key, 0))
            if item["spend"] == 0:
                item["revenue"] = 0.0
            # If an export repeats a pair, its later occurrence is the current
            # reported value rather than an additional independent observation.
            latest[(row_day, cid)] = item
        return list(latest.values())

    def _rates(self, history: list[dict[str, Any]]):
        total_spend = sum(row["spend"] for row in history)
        total_revenue = sum(row["revenue"] for row in history)
        global_rate = total_revenue / total_spend if total_spend > 0 else 1.0
        global_rate = min(20.0, max(0.05, global_rate))

        format_totals: dict[str, list[float]] = defaultdict(lambda: [0.0, 0.0])
        hook_totals: dict[str, list[float]] = defaultdict(lambda: [0.0, 0.0])
        for row in history:
            creative = self.by_id[row["creative_id"]]
            fmt = str(creative.get("format") or "unknown")
            hook = str(creative.get("hook_type") or "unknown")
            format_totals[fmt][0] += row["spend"]
            format_totals[fmt][1] += row["revenue"]
            hook_totals[hook][0] += row["spend"]
            hook_totals[hook][1] += row["revenue"]

        return global_rate, total_spend, total_revenue, format_totals, hook_totals

    def allocate(self, day: int, history: list[dict]) -> dict[str, float]:
        try:
            decision_day = int(day)
        except (TypeError, ValueError, OverflowError):
            decision_day = 1
        clean = self._clean_history(decision_day, history)
        global_rate, total_spend, total_revenue, format_totals, hook_totals = self._rates(clean)

        lifetime: dict[str, list[float]] = {cid: [0.0, 0.0, 0.0] for cid in self.ids}
        recent: dict[str, list[float]] = {cid: [0.0, 0.0, 0.0] for cid in self.ids}
        for row in clean:
            cid = row["creative_id"]
            lifetime[cid][0] += row["spend"]
            lifetime[cid][1] += row["revenue"]
            lifetime[cid][2] += row["impressions"]
            if decision_day - 7 <= row["day"] < decision_day:
                recent[cid][0] += row["spend"]
                recent[cid][1] += row["revenue"]
                recent[cid][2] += row["impressions"]

        allocations: dict[str, float] = {}
        scores: dict[str, float] = {}
        floors: dict[str, float] = {}
        for cid in self.ids:
            creative = self.by_id[cid]
            fmt = str(creative.get("format") or "unknown")
            hook = str(creative.get("hook_type") or "unknown")
            spend, revenue, impressions = lifetime[cid]
            other_spend = max(0.0, total_spend - spend)
            other_revenue = max(0.0, total_revenue - revenue)
            prior_global = other_revenue / other_spend if other_spend > 0 else global_rate
            prior_global = min(20.0, max(0.05, prior_global))

            def group_rate(totals: dict[str, list[float]], key: str) -> float:
                group_spend, group_revenue = totals.get(key, [0.0, 0.0])
                group_spend = max(0.0, group_spend - spend)
                group_revenue = max(0.0, group_revenue - revenue)
                rate = ((group_revenue + self._META_GROUP_PRIOR_SPEND * prior_global) /
                        (group_spend + self._META_GROUP_PRIOR_SPEND))
                return min(prior_global * 1.75, max(prior_global * 0.55, rate))

            format_rate = group_rate(format_totals, fmt)
            hook_rate = group_rate(hook_totals, hook)
            metadata_prior = prior_global * math.exp(
                0.5 * self._META_LOG_WEIGHT *
                (math.log(format_rate / prior_global) + math.log(hook_rate / prior_global))
            )
            metadata_prior = min(prior_global * 1.35, max(prior_global * 0.65, metadata_prior))

            long_rate = ((revenue + self._CREATIVE_PRIOR_SPEND * metadata_prior) /
                         (spend + self._CREATIVE_PRIOR_SPEND))
            long_rate = min(20.0, max(0.05, long_rate))
            recent_spend, recent_revenue, _ = recent[cid]
            recent_rate = ((recent_revenue + self._RECENT_PRIOR_SPEND * long_rate) /
                           (recent_spend + self._RECENT_PRIOR_SPEND))
            recent_rate = min(20.0, max(0.05, recent_rate))
            recency_weight = 0.60 * recent_spend / (recent_spend + self._RECENT_PRIOR_SPEND)
            posterior_mean = (1.0 - recency_weight) * long_rate + recency_weight * recent_rate

            # Uncertainty declines with evidence. The bonus is intentionally
            # modest; it supports discovery without treating a prior as proof.
            uncertainty_fraction = math.sqrt(
                self._UNCERTAINTY_PRIOR_SPEND /
                (self._UNCERTAINTY_PRIOR_SPEND + spend)
            )
            uncertainty_fraction = min(1.0, uncertainty_fraction)
            score = posterior_mean * (1.0 + self._EXPLORATION_BONUS * uncertainty_fraction)
            scores[cid] = max(0.05, score) ** self._SCORE_POWER
            floors[cid] = self._SERVED_FLOOR if spend > 0 or impressions > 0 else self._COLD_START_FLOOR

        # Reserve a small explicit floor for every candidate, with a little
        # extra for never-served creatives. The remainder follows bounded
        # posterior scores and is redistributed when a creative hits its cap.
        if sum(floors.values()) >= self.daily_budget:
            floor = self.daily_budget / len(self.ids)
            return {cid: floor / self.daily_budget for cid in self.ids}
        allocations.update(floors)
        remaining = self.daily_budget - sum(allocations.values())
        maximum = self.daily_budget * self._MAX_ALLOCATION_FRACTION
        eligible = set(self.ids)
        while remaining > 1e-8 and eligible:
            weight_total = sum(scores[cid] for cid in eligible)
            if weight_total <= 0:
                weight_total = float(len(eligible))
                weights = {cid: 1.0 for cid in eligible}
            else:
                weights = {cid: scores[cid] for cid in eligible}
            capped = []
            for cid in sorted(eligible):
                proposed = remaining * weights[cid] / weight_total
                room = max(0.0, maximum - allocations[cid])
                if proposed >= room:
                    allocations[cid] += room
                    capped.append(cid)
            if capped:
                remaining = self.daily_budget - sum(allocations.values())
                eligible.difference_update(capped)
                continue
            for cid in eligible:
                allocations[cid] += remaining * weights[cid] / weight_total
            remaining = 0.0

        # Normalize floating-point residue so the public interface always
        # returns shares summing to one and includes every supplied creative.
        total = sum(allocations.values())
        if total <= 0 or not math.isfinite(total):
            return {cid: 1.0 / len(self.ids) for cid in self.ids}
        return {cid: max(0.0, allocations[cid] / total) for cid in self.ids}
