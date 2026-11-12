"""Historically calibrated delivery simulator and transparent benchmark rules.

All parameters that describe the simulated world live in config.json. This
module is for evaluation only; a policy must not import it or read that file.
"""

from __future__ import annotations

import csv
import hashlib
import json
import math
import random
from collections import defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
CONFIG_PATH = ROOT / "config.json"
HISTORY_FIELDS = ("day", "creative_id", "budget", "spend", "impressions", "clicks", "purchases", "revenue")
METRICS = ("budget", "spend", "impressions", "clicks", "purchases", "revenue")
DAILY_BUDGET = 2000.0
FIRST_EVAL_DAY = 61
LAST_EVAL_DAY = 90


def load_json(path: Path = CONFIG_PATH) -> dict[str, Any]:
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def load_creatives(path: Path = DATA / "creatives.csv") -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def load_initial_history(path: Path = DATA / "daily_reported.csv") -> list[dict[str, Any]]:
    """Load the end-of-day-60 reported snapshot, not later-finalized outcomes."""
    rows: list[dict[str, Any]] = []
    with path.open(newline="", encoding="utf-8-sig") as f:
        for raw in csv.DictReader(f):
            row: dict[str, Any] = {
                "day": int(raw["day"]), "creative_id": raw["creative_id"],
            }
            for metric in METRICS:
                value = float(raw[metric])
                row[metric] = int(value) if metric in ("impressions", "clicks", "purchases") else value
            rows.append(row)
    return rows


def _stable_rng(seed: int, *parts: object) -> random.Random:
    """Stable across Python processes and independent of call ordering."""
    payload = "|".join([str(seed), *(str(part) for part in parts)]).encode("utf-8")
    token = hashlib.blake2b(payload, digest_size=16).digest()
    return random.Random(int.from_bytes(token, "big"))


def _mean_delivery(dynamics: dict[str, float]) -> float:
    probability = float(dynamics["delivery_underfill_probability"])
    low = float(dynamics["delivery_underfill_factor_low"])
    high = float(dynamics["delivery_underfill_factor_high"])
    creative_delivery = (1.0 - probability) + probability * (low + high) / 2.0
    return float(dynamics.get("account_pacing_mean", 1.0)) * creative_delivery


def _sample_count(mean: float, rng: random.Random, overdispersion: float = 1.0) -> int:
    if mean <= 0:
        return 0
    # Gaussian approximation to a Poisson/binomial count is adequate at the
    # thousands of impressions and dozens of clicks seen at this budget.
    sd = math.sqrt(mean) * overdispersion
    return max(0, int(round(rng.gauss(mean, sd))))


class SimulatedAccount:
    """One 30-day counterfactual world with protocol-shaped history."""

    def __init__(self, seed: int, scenario: str = "baseline", *,
                 config: dict[str, Any] | None = None,
                 creatives: list[dict[str, str]] | None = None,
                 initial_history: list[dict[str, Any]] | None = None):
        self.seed = int(seed)
        self.config = config if config is not None else load_json()
        if scenario not in self.config["scenarios"]:
            raise ValueError(f"unknown scenario: {scenario}")
        self.scenario = scenario
        self.dynamics = dict(self.config["dynamics"])
        self.dynamics.update(self.config["scenarios"][scenario])
        self.creatives = creatives if creatives is not None else load_creatives()
        self.creative_ids = [c["creative_id"] for c in self.creatives]
        if len(self.creative_ids) != 50 or len(set(self.creative_ids)) != len(self.creative_ids):
            raise ValueError("simulation expects 50 distinct creatives")
        if set(self.creative_ids) != set(self.config["creatives"]):
            raise ValueError("config.json must include calibrated parameters for all 50 creatives")
        self.daily_budget = DAILY_BUDGET
        self.history = [dict(row) for row in (initial_history if initial_history is not None else load_initial_history())]
        if any(int(row["day"]) >= FIRST_EVAL_DAY for row in self.history):
            raise ValueError("initial policy history must not include evaluation days")
        self.next_day = FIRST_EVAL_DAY
        self.age_at_start = {cid: int(self.config["creatives"][cid]["starting_age_days"]) for cid in self.creative_ids}
        self.latent_roas = self._draw_creative_effectiveness()
        # Draw market state lazily for the current day only. The oracle cannot
        # inspect a precomputed table of future market shocks.
        self._current_market_day: int | None = None
        self._current_market_value: float | None = None
        self._current_pacing_day: int | None = None
        self._current_pacing_value: float | None = None

    def _draw_creative_effectiveness(self) -> dict[str, float]:
        result = {}
        uncertainty_multiplier = float(self.dynamics.get("uncertainty_multiplier", 1.0))
        cold_multiplier = float(self.dynamics.get("cold_start_uncertainty_multiplier", 1.0))
        shift_sd = float(self.dynamics.get("effectiveness_log_shift_sd", 0.0))
        for cid in self.creative_ids:
            item = self.config["creatives"][cid]
            sigma = float(item["log_sd"]) * uncertainty_multiplier
            if item["calibration_source"] == "metadata_prior_no_observed_outcomes":
                sigma *= cold_multiplier
            sigma = math.sqrt(sigma * sigma + shift_sd * shift_sd)
            rng = _stable_rng(self.seed, "creative-effectiveness", cid)
            # Mean-preserving lognormal world draw. The central rate remains a
            # prior/posterior mean; this draw is simulator ground truth.
            center = float(item["central_roas"])
            rate = math.exp(math.log(center) - 0.5 * sigma * sigma + sigma * rng.gauss(0, 1))
            result[cid] = rate
        return result

    def _draw_market(self, day: int) -> float:
        offset = day - FIRST_EVAL_DAY
        drift = float(self.dynamics.get("market_daily_drift", 0.0))
        sigma = float(self.dynamics.get("market_log_noise_sd", 0.0))
        rng = _stable_rng(self.seed, "market", day)
        random_factor = math.exp(-0.5 * sigma * sigma + sigma * rng.gauss(0, 1))
        return max(0.25, (1.0 + drift) ** offset * random_factor)

    def current_market_factor(self, day: int) -> float:
        if day != self.next_day:
            raise ValueError("only the current evaluation day's market state is available")
        if self._current_market_day != day:
            self._current_market_day = day
            self._current_market_value = self._draw_market(day)
        assert self._current_market_value is not None
        return self._current_market_value

    def _current_account_pacing_factor(self, day: int) -> float:
        if day != self.next_day:
            raise ValueError("only the current day's realized pacing factor is available")
        if self._current_pacing_day != day:
            mean = float(self.dynamics.get("account_pacing_mean", 1.0))
            sigma = float(self.dynamics.get("account_pacing_log_noise_sd", 0.0))
            rng = _stable_rng(self.seed, "account-pacing", day)
            self._current_pacing_day = day
            self._current_pacing_value = min(
                1.0, mean * math.exp(-0.5 * sigma * sigma + sigma * rng.gauss(0, 1))
            )
        assert self._current_pacing_value is not None
        return self._current_pacing_value

    def policy_history(self, day: int) -> list[dict[str, Any]]:
        """Return only rows available before `day`; no simulator parameters."""
        if day != self.next_day:
            raise ValueError(f"expected day {self.next_day}, got history request for {day}")
        rows = [dict(row) for row in self.history if int(row["day"]) < day]
        if rows and max(int(row["day"]) for row in rows) >= day:
            raise AssertionError("future row leaked into policy history")
        return rows

    def _delivery_factor(self, day: int, cid: str) -> float:
        probability = float(self.dynamics["delivery_underfill_probability"])
        rng = _stable_rng(self.seed, "delivery", day, cid)
        if rng.random() < probability:
            low = float(self.dynamics["delivery_underfill_factor_low"])
            high = float(self.dynamics["delivery_underfill_factor_high"])
            return rng.uniform(low, high)
        return 1.0

    def expected_revenue(self, creative_id: str, allocation: float, day: int) -> float:
        """Expected current-day revenue, exposed for oracle use only."""
        if allocation < 1.0:
            return 0.0
        mean_spend = allocation * _mean_delivery(self.dynamics)
        reference = float(self.config["calibration"]["reference_daily_spend_usd"])
        elasticity = float(self.dynamics["spend_elasticity"])
        saturation = (mean_spend / reference) ** (-elasticity)
        age = self.age_at_start[creative_id] + day - FIRST_EVAL_DAY
        fatigue = math.exp(-float(self.dynamics["fatigue_log_decay_per_day"]) * age)
        return mean_spend * self.latent_roas[creative_id] * saturation * fatigue * self.current_market_factor(day)

    def step(self, day: int, allocation: dict[str, float]) -> list[dict[str, Any]]:
        """Deliver one dollar-valued allocation and append resulting history rows.

        Values are dollars, not shares. Unknown IDs are ignored. A total above
        $2,000 is scaled down; unused budget is allowed and is not carried.
        Allocations below $1 have zero recorded budget and no delivery.
        """
        if day != self.next_day or day > LAST_EVAL_DAY:
            raise ValueError(f"expected sequential day {self.next_day} within days 61-90")
        dollars = {cid: 0.0 for cid in self.creative_ids}
        for cid, raw_amount in allocation.items():
            if cid not in dollars:
                continue
            amount = float(raw_amount)
            if not math.isfinite(amount) or amount < 0:
                raise ValueError("allocations must be finite and nonnegative")
            dollars[cid] = amount
        total = sum(dollars.values())
        if total > self.daily_budget:
            scale = self.daily_budget / total
            dollars = {cid: amount * scale for cid, amount in dollars.items()}

        prior_ids = {str(row["creative_id"]) for row in self.history}
        generated: list[dict[str, Any]] = []
        calibration = self.config["calibration"]
        for cid in self.creative_ids:
            amount = dollars[cid]
            if amount < 1.0:
                # Previously active creatives retain a zero row. A cold-start
                # creative with no actual delivery still has no history row.
                if cid not in prior_ids:
                    continue
                recorded_budget = 0.0
                spend = impressions = clicks = purchases = revenue = 0
            else:
                recorded_budget = amount
                spend = amount * self._current_account_pacing_factor(day) * self._delivery_factor(day, cid)
                cpm = float(calibration["cpm"])
                expected_impressions = spend * 1000.0 / cpm
                overdispersion = float(self.dynamics.get("impression_overdispersion", 1.0))
                impressions = _sample_count(expected_impressions,
                                            _stable_rng(self.seed, "impressions", day, cid), overdispersion)
                clicks = _sample_count(impressions * float(calibration["global_ctr"]),
                                       _stable_rng(self.seed, "clicks", day, cid))
                rate_ratio = self.latent_roas[cid] / float(calibration["global_roas"])
                reference = float(calibration["reference_daily_spend_usd"])
                expected_spend = amount * _mean_delivery(self.dynamics)
                saturation = (max(expected_spend, 1e-9) / reference) ** (-float(self.dynamics["spend_elasticity"]))
                age = self.age_at_start[cid] + day - FIRST_EVAL_DAY
                fatigue = math.exp(-float(self.dynamics["fatigue_log_decay_per_day"]) * age)
                market = self.current_market_factor(day)
                purchase_rate = min(1.0, float(calibration["global_purchase_per_click"])
                                    * rate_ratio * saturation * fatigue * market)
                purchases = _sample_count(clicks * purchase_rate,
                                          _stable_rng(self.seed, "purchases", day, cid))
                mean_aov = float(calibration["mean_order_value"])
                order_value_cv = float(self.dynamics.get("order_value_cv", 0.0))
                aov_log_sd = math.sqrt(math.log1p(order_value_cv * order_value_cv) / purchases) if purchases else 0.0
                revenue = (purchases * mean_aov
                           * math.exp(-0.5 * aov_log_sd * aov_log_sd + aov_log_sd
                                      * _stable_rng(self.seed, "revenue", day, cid).gauss(0, 1))) if purchases else 0.0
                revenue = round(revenue, 2)
                spend = min(amount, round(spend, 2))
            row = {"day": day, "creative_id": cid, "budget": recorded_budget,
                   "spend": spend, "impressions": impressions, "clicks": clicks,
                   "purchases": purchases, "revenue": revenue}
            generated.append(row)
        self.history.extend(generated)
        self.next_day += 1
        return [dict(row) for row in generated]


def uniform_allocation(creatives: list[dict[str, str]], daily_budget: float = DAILY_BUDGET) -> dict[str, float]:
    share = daily_budget / len(creatives)
    return {c["creative_id"]: share for c in creatives}


def windowed_greedy_allocation(creatives: list[dict[str, str]], history: list[dict[str, Any]],
                               day: int, daily_budget: float = DAILY_BUDGET) -> dict[str, float]:
    """BRIEF.md B2: trailing 7-day ROAS, 2,000-impression eligibility."""
    ids = [c["creative_id"] for c in creatives]
    lower_day = day - 7
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in history:
        row_day = int(row["day"])
        if lower_day <= row_day < day and row["creative_id"] in ids:
            grouped[str(row["creative_id"])].append(row)
    total_spend = sum(float(r["spend"]) for rows in grouped.values() for r in rows)
    total_revenue = sum(float(r["revenue"]) for rows in grouped.values() for r in rows)
    population_rate = total_revenue / total_spend if total_spend > 0 else 0.0
    rates: list[tuple[str, float]] = []
    for cid in ids:
        rows = grouped[cid]
        spend = sum(float(r["spend"]) for r in rows)
        impressions = sum(int(r["impressions"]) for r in rows)
        revenue = sum(float(r["revenue"]) for r in rows)
        rate = revenue / spend if impressions >= 2000 and spend > 0 else population_rate
        rates.append((cid, rate))
    ranked = sorted(rates, key=lambda item: (-item[1], item[0]))
    winners = {cid for cid, _ in ranked[:5]}
    other_count = len(ids) - len(winners)
    return {cid: daily_budget * (0.75 / 5 if cid in winners else 0.25 / other_count)
            for cid in ids}


def clairvoyant_allocation(environment: SimulatedAccount, day: int) -> dict[str, float]:
    """Water-fill expected concave revenue using only current latent state.

    It knows sampled current creative effectiveness, fatigue, today's market
    factor, delivery expectation, and the configured diminishing-return curve.
    It never sees the current day's random delivery or outcome draws, nor any
    future market factors. The objective is separable and concave for elasticity
    in (0, 1), so equalizing marginal expected revenue gives the optimum.
    """
    budget = environment.daily_budget
    ids = environment.creative_ids
    if budget < len(ids):
        raise ValueError("oracle requires at least $1 per creative for its water-fill solution")
    elasticity = float(environment.dynamics["spend_elasticity"])
    if not 0 < elasticity < 1:
        raise ValueError("clairvoyant requires spend elasticity in (0, 1)")
    delivery = _mean_delivery(environment.dynamics)
    reference = float(environment.config["calibration"]["reference_daily_spend_usd"])
    coefficients: dict[str, float] = {}
    for cid in ids:
        age = environment.age_at_start[cid] + day - FIRST_EVAL_DAY
        fatigue = math.exp(-float(environment.dynamics["fatigue_log_decay_per_day"]) * age)
        # For allocation a>=1, expected revenue = coefficient * a^(1-epsilon).
        coefficients[cid] = (environment.latent_roas[cid] * fatigue
                              * environment.current_market_factor(day)
                              * reference ** elasticity * delivery ** (1 - elasticity))

    def allocation_at_marginal(marginal: float) -> dict[str, float]:
        allocation: dict[str, float] = {}
        for cid in ids:
            unconstrained = (coefficients[cid] * (1 - elasticity) / marginal) ** (1 / elasticity)
            if unconstrained >= 1.0:
                allocation[cid] = unconstrained
            elif coefficients[cid] > marginal:
                # Starting a creative has a $1 activation threshold. Compare
                # its expected revenue at $1 with the budget's shadow value.
                allocation[cid] = 1.0
            else:
                allocation[cid] = 0.0
        return allocation

    low, high = 1e-12, max(coefficients.values()) * 1.000001
    for _ in range(100):
        mid = (low + high) / 2
        if sum(allocation_at_marginal(mid).values()) > budget:
            low = mid
        else:
            high = mid
    allocation = allocation_at_marginal(high)
    # At an activation discontinuity the active set can leave less than $1
    # unused. Put that residue on the active creative with highest marginal
    # expected revenue; this preserves the budget and the discrete threshold.
    total = sum(allocation.values())
    remainder = budget - total
    if remainder > 1e-8:
        active = [cid for cid, amount in allocation.items() if amount >= 1.0]
        if not active:
            active = [max(ids, key=lambda cid: coefficients[cid])]
        target = max(active, key=lambda cid: coefficients[cid] * (1 - elasticity)
                     * max(allocation[cid], 1.0) ** (-elasticity))
        allocation[target] += remainder
    return allocation
