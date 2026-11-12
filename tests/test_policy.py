from __future__ import annotations

import ast
import inspect
import unittest
from pathlib import Path

from policy import Policy
from simulator import load_creatives, load_initial_history


class PolicyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.creatives = load_creatives()
        cls.history = load_initial_history()
        cls.ids = {creative["creative_id"] for creative in cls.creatives}
        cls.cold_ids = {creative["creative_id"] for creative in cls.creatives if not creative["launch_day"]}

    def assert_valid_allocation(self, allocation: dict[str, float]) -> None:
        self.assertEqual(set(allocation), self.ids)
        self.assertTrue(all(value >= 0 for value in allocation.values()))
        self.assertAlmostEqual(sum(allocation.values()), 1.0, places=10)

    def test_required_interface(self) -> None:
        self.assertEqual(list(inspect.signature(Policy.__init__).parameters),
                         ["self", "creatives", "daily_budget", "seed"])
        self.assertEqual(list(inspect.signature(Policy.allocate).parameters),
                         ["self", "day", "history"])
        policy = Policy(self.creatives, 2000.0, 1)
        self.assert_valid_allocation(policy.allocate(61, self.history))

    def test_all_creatives_are_returned_and_budget_is_fully_allocated(self) -> None:
        policy = Policy(self.creatives, 2000.0, 2)
        allocation = policy.allocate(61, self.history)
        self.assert_valid_allocation(allocation)
        self.assertAlmostEqual(sum(value * 2000 for value in allocation.values()), 2000.0)
        self.assertLessEqual(max(value * 2000 for value in allocation.values()), 400.0 + 1e-6)

    def test_empty_missing_and_malformed_history(self) -> None:
        policy = Policy(self.creatives, 2000.0, 3)
        malformed = [None, {}, {"day": "bad", "creative_id": "CR001"},
                     {"day": 60.9, "creative_id": "CR001", "spend": 2000, "revenue": 200000},
                     {"day": 0, "creative_id": "CR001", "spend": 2000, "revenue": 200000},
                     {"day": 60, "creative_id": "UNKNOWN", "spend": 100, "revenue": 1000},
                     {"day": 60, "creative_id": "CR001", "spend": "bad", "revenue": float("nan")},
                     {"day": 59, "creative_id": "CR004", "spend": 0, "revenue": 1000000},
                     {"day": 60, "creative_id": "CR002", "spend": -10, "revenue": -100},
                     {"day": 62, "creative_id": "CR003", "spend": 2000, "revenue": 20000}]
        self.assert_valid_allocation(policy.allocate(61, []))
        self.assert_valid_allocation(policy.allocate(61, malformed))
        self.assertEqual(policy.allocate(61, malformed), policy.allocate(61, []))

    def test_zero_spend_rows_do_not_create_infinite_rates(self) -> None:
        policy = Policy(self.creatives, 2000.0, 4)
        zero_rows = [{"day": 60, "creative_id": cid, "budget": 0, "spend": 0,
                      "impressions": 0, "clicks": 0, "purchases": 0, "revenue": 0}
                     for cid in self.ids]
        self.assert_valid_allocation(policy.allocate(61, zero_rows))

    def test_never_served_creatives_get_a_controlled_opportunity(self) -> None:
        policy = Policy(self.creatives, 2000.0, 5)
        allocation = policy.allocate(61, self.history)
        self.assertTrue(self.cold_ids)
        for cid in self.cold_ids:
            self.assertGreaterEqual(allocation[cid] * 2000, 8.0 - 1e-8)

    def test_repeated_calls_same_inputs_are_identical(self) -> None:
        policy = Policy(self.creatives, 2000.0, 6)
        first = policy.allocate(61, self.history)
        second = policy.allocate(61, self.history)
        self.assertEqual(first, second)

    def test_same_seed_and_inputs_are_deterministic(self) -> None:
        first = Policy(self.creatives, 2000.0, 7).allocate(61, self.history)
        second = Policy(self.creatives, 2000.0, 7).allocate(61, self.history)
        self.assertEqual(first, second)

    def test_skipped_days_do_not_require_internal_sequence_state(self) -> None:
        policy = Policy(self.creatives, 2000.0, 8)
        allocation = policy.allocate(63, self.history)
        self.assert_valid_allocation(allocation)

    def test_policy_ignores_future_history_rows(self) -> None:
        policy = Policy(self.creatives, 2000.0, 9)
        future = {"day": 99, "creative_id": next(iter(self.ids)), "budget": 2000,
                  "spend": 2000, "impressions": 1_000_000, "clicks": 100_000,
                  "purchases": 100_000, "revenue": 10_000_000}
        self.assertEqual(policy.allocate(61, self.history),
                         policy.allocate(61, self.history + [future]))

    def test_policy_has_no_simulator_config_or_file_access_imports(self) -> None:
        source = Path(__file__).resolve().parents[1] / "policy.py"
        tree = ast.parse(source.read_text(encoding="utf-8"))
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module.split(".")[0])
        self.assertNotIn("simulator", imported)
        self.assertNotIn("config", imported)
        self.assertFalse(any(isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                             and node.func.id == "open" for node in ast.walk(tree)))


if __name__ == "__main__":
    unittest.main()

