from __future__ import annotations

import unittest

from simulator import (
    DAILY_BUDGET, FIRST_EVAL_DAY, LAST_EVAL_DAY, SimulatedAccount,
    clairvoyant_allocation, load_creatives, load_initial_history,
    uniform_allocation, windowed_greedy_allocation,
)


class SimulatorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.creatives = load_creatives()
        cls.initial = load_initial_history()
        cls.ids = [row["creative_id"] for row in cls.creatives]
        cls.cold_ids = [row["creative_id"] for row in cls.creatives if not row["launch_day"]]
        cls.served_ids = [row["creative_id"] for row in cls.creatives if row["launch_day"]]

    def test_reproducibility_under_identical_seeds(self) -> None:
        env_a = SimulatedAccount(7, "baseline", creatives=self.creatives, initial_history=self.initial)
        env_b = SimulatedAccount(7, "baseline", creatives=self.creatives, initial_history=self.initial)
        action = uniform_allocation(self.creatives)
        for day in range(61, 64):
            self.assertEqual(env_a.step(day, action), env_b.step(day, action))

    def test_budget_constraints_and_overallocation_scaling(self) -> None:
        env = SimulatedAccount(8, creatives=self.creatives, initial_history=self.initial)
        rows = env.step(61, {cid: 100.0 for cid in self.ids})
        self.assertLessEqual(sum(row["budget"] for row in rows), DAILY_BUDGET + 1e-8)
        self.assertLessEqual(sum(row["spend"] for row in rows), DAILY_BUDGET + 1e-8)
        self.assertTrue(all(row["spend"] <= row["budget"] + 1e-8 for row in rows))
        self.assertAlmostEqual(sum(row["budget"] for row in rows), DAILY_BUDGET, places=6)

    def test_cold_start_creatives_have_no_fabricated_initial_history(self) -> None:
        env = SimulatedAccount(9, creatives=self.creatives, initial_history=self.initial)
        history = env.policy_history(61)
        history_ids = {row["creative_id"] for row in history}
        self.assertFalse(history_ids.intersection(self.cold_ids))
        rows = env.step(61, {self.cold_ids[0]: 25.0})
        cold_row = next(row for row in rows if row["creative_id"] == self.cold_ids[0])
        self.assertGreater(cold_row["impressions"], 0)
        self.assertEqual(cold_row["day"], 61)

    def test_zero_spend_and_sub_dollar_allocations(self) -> None:
        env = SimulatedAccount(10, creatives=self.creatives, initial_history=self.initial)
        served, cold = self.served_ids[0], self.cold_ids[0]
        rows = env.step(61, {served: 0.99, cold: 0.99})
        served_row = next(row for row in rows if row["creative_id"] == served)
        self.assertEqual(served_row["budget"], 0.0)
        self.assertEqual(served_row["spend"], 0.0)
        self.assertEqual(served_row["impressions"], 0)
        self.assertNotIn(cold, {row["creative_id"] for row in rows})
        self.assertNotIn(cold, {row["creative_id"] for row in env.policy_history(62)})

    def test_allocation_benchmarks_sum_and_cover_all_creatives(self) -> None:
        uniform = uniform_allocation(self.creatives)
        greedy = windowed_greedy_allocation(self.creatives, self.initial, 61)
        env = SimulatedAccount(11, creatives=self.creatives, initial_history=self.initial)
        oracle = clairvoyant_allocation(env, 61)
        for allocation in (uniform, greedy, oracle):
            self.assertEqual(set(allocation), set(self.ids))
            self.assertAlmostEqual(sum(allocation.values()), DAILY_BUDGET, places=5)
            self.assertTrue(all(value >= 0 for value in allocation.values()))
        self.assertEqual(sum(value > 0 for value in greedy.values()), 50)
        oracle_value = sum(env.expected_revenue(cid, amount, 61) for cid, amount in oracle.items())
        uniform_value = sum(env.expected_revenue(cid, amount, 61) for cid, amount in uniform.items())
        self.assertGreaterEqual(oracle_value + 1e-6, uniform_value)

    def test_progression_is_exactly_days_61_through_90(self) -> None:
        env = SimulatedAccount(12, creatives=self.creatives, initial_history=self.initial)
        for day in range(FIRST_EVAL_DAY, LAST_EVAL_DAY + 1):
            self.assertLess(max(row["day"] for row in env.policy_history(day)), day)
            env.step(day, uniform_allocation(self.creatives))
        self.assertEqual(env.next_day, 91)
        with self.assertRaises(ValueError):
            env.step(91, uniform_allocation(self.creatives))

    def test_generated_metrics_are_nonnegative(self) -> None:
        env = SimulatedAccount(13, "greater_uncertainty", creatives=self.creatives,
                               initial_history=self.initial)
        for day in range(61, 65):
            rows = env.step(day, uniform_allocation(self.creatives))
            for row in rows:
                for key in ("budget", "spend", "impressions", "clicks", "purchases", "revenue"):
                    self.assertGreaterEqual(row[key], 0)
                self.assertLessEqual(row["clicks"], row["impressions"])
                self.assertLessEqual(row["purchases"], row["clicks"])
                self.assertEqual(row["revenue"] > 0, row["purchases"] > 0)

    def test_policy_history_has_no_future_rows_and_oracle_cannot_read_future_market(self) -> None:
        env = SimulatedAccount(14, creatives=self.creatives, initial_history=self.initial)
        before = env.policy_history(61)
        self.assertEqual(max(row["day"] for row in before), 60)
        expected_fields = {"day", "creative_id", "budget", "spend", "impressions",
                           "clicks", "purchases", "revenue"}
        self.assertTrue(all(set(row) == expected_fields for row in before))
        self.assertFalse(hasattr(env, "_market_factors"))
        with self.assertRaises(ValueError):
            env.current_market_factor(62)
        clairvoyant_allocation(env, 61)
        self.assertEqual(env._current_market_day, 61)
        rows = env.step(61, uniform_allocation(self.creatives))
        self.assertTrue(all(row["day"] == 61 for row in rows))
        after = env.policy_history(62)
        self.assertEqual(max(row["day"] for row in after), 61)
        self.assertNotIn(62, {row["day"] for row in after})

    def test_windowed_greedy_ignores_future_rows(self) -> None:
        future = {"day": 62, "creative_id": self.ids[0], "budget": 2000, "spend": 2000,
                  "impressions": 100000, "clicks": 100000, "purchases": 100000,
                  "revenue": 1000000}
        base = windowed_greedy_allocation(self.creatives, self.initial, 61)
        with_future = windowed_greedy_allocation(self.creatives, self.initial + [future], 61)
        self.assertEqual(base, with_future)

    def test_windowed_greedy_handles_zero_spend_and_population_fallback(self) -> None:
        history = [{"day": 60, "creative_id": cid, "budget": 0.0, "spend": 0.0,
                    "impressions": 0, "clicks": 0, "purchases": 0, "revenue": 0.0}
                   for cid in self.ids]
        allocation = windowed_greedy_allocation(self.creatives, history, 61)
        self.assertAlmostEqual(sum(allocation.values()), DAILY_BUDGET)
        self.assertEqual(len(allocation), 50)
        self.assertTrue(all(value >= 0 for value in allocation.values()))


if __name__ == "__main__":
    unittest.main()
