import copy
from pathlib import Path
import subprocess
import sys
import unittest

from tools.relation_discrimination import (
    REQUIRED_AXES,
    RelationDiscriminationError,
    classify_outcome_mismatch,
    evaluate_relation,
    load_suite,
    validate_relation_discrimination,
)


ROOT = Path(__file__).resolve().parents[1]


class RelationDiscriminationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.suite = load_suite()

    def _collapsed_evaluator(self, axis: str):
        def evaluator(policy, before, after):
            collapsed = copy.deepcopy(policy)
            if axis == "identity":
                collapsed["identity_policy"] = "anchored"
            elif axis == "relation_type":
                collapsed["relation_type_policy"] = "typed-exact"
            elif axis == "multiplicity":
                collapsed["multiplicity_policy"] = "multiset-exact"
            elif axis == "direction":
                collapsed["direction_policy"] = "directed-exact"
            elif axis == "scope":
                collapsed["scope_policy"] = "global"
                collapsed["scope_anchor"] = None
            else:
                self.fail(f"unknown mutation axis: {axis}")
            return evaluate_relation(collapsed, before, after)

        return evaluator

    def _assert_axis_collapse_is_killed(self, axis: str) -> None:
        with self.assertRaisesRegex(
            RelationDiscriminationError,
            f"UNRESOLVED_RELATION_DISCRIMINATION:{axis}",
        ):
            validate_relation_discrimination(
                self.suite,
                evaluator=self._collapsed_evaluator(axis),
            )

    def test_canonical_suite_separates_every_required_axis(self) -> None:
        report = validate_relation_discrimination(self.suite)
        self.assertEqual(report["status"], "PASS")
        self.assertEqual(report["required_axes"], 5)
        self.assertEqual(report["separated_axes"], 5)
        self.assertEqual(set(report["matrix"]), set(REQUIRED_AXES))
        for axis in REQUIRED_AXES:
            with self.subTest(axis=axis):
                self.assertEqual(report["matrix"][axis]["status"], "SEPARATED")
                self.assertTrue(report["matrix"][axis]["separating_witnesses"])

    def test_identity_axis_collapse_is_killed(self) -> None:
        self._assert_axis_collapse_is_killed("identity")

    def test_relation_type_axis_collapse_is_killed(self) -> None:
        self._assert_axis_collapse_is_killed("relation_type")

    def test_multiplicity_axis_collapse_is_killed(self) -> None:
        self._assert_axis_collapse_is_killed("multiplicity")

    def test_direction_axis_collapse_is_killed(self) -> None:
        self._assert_axis_collapse_is_killed("direction")

    def test_scope_axis_collapse_is_killed(self) -> None:
        self._assert_axis_collapse_is_killed("scope")

    def test_missing_required_axis_is_rejected(self) -> None:
        mutated = copy.deepcopy(self.suite)
        mutated["required_axes"].remove("scope")
        with self.assertRaisesRegex(RelationDiscriminationError, "REQUIRED_AXIS_SET_MISMATCH"):
            validate_relation_discrimination(mutated)

    def test_missing_required_witness_is_rejected(self) -> None:
        mutated = copy.deepcopy(self.suite)
        mutated["witnesses"] = [
            witness
            for witness in mutated["witnesses"]
            if witness["witness_id"] != "direction-reversal"
        ]
        with self.assertRaisesRegex(RelationDiscriminationError, "MISSING_REQUIRED_WITNESS:direction"):
            validate_relation_discrimination(mutated)

    def test_mutated_expected_separation_is_rejected(self) -> None:
        mutated = copy.deepcopy(self.suite)
        identity_pair = mutated["policy_pairs"][0]
        identity_pair["expected_outcomes"]["identity-alias"]["right"] = "VIOLATED"
        with self.assertRaisesRegex(RelationDiscriminationError, "DECLARED_SEPARATION_MISSING:identity"):
            validate_relation_discrimination(mutated)

    def test_expected_violation_upgraded_to_preserved_is_classified_unsafe(self) -> None:
        mutated = copy.deepcopy(self.suite)
        identity_pair = mutated["policy_pairs"][0]
        identity_pair["expected_outcomes"]["positive-control"]["left"] = "VIOLATED"
        with self.assertRaisesRegex(RelationDiscriminationError, "UNSAFE_FALSE_PRESERVATION"):
            validate_relation_discrimination(mutated)

    def test_expected_unverifiable_upgraded_to_preserved_is_classified_unsafe(self) -> None:
        mutated = copy.deepcopy(self.suite)
        identity_pair = mutated["policy_pairs"][0]
        identity_pair["expected_outcomes"]["positive-control"]["left"] = "UNVERIFIABLE"
        with self.assertRaisesRegex(RelationDiscriminationError, "UNSAFE_UNVERIFIABLE_UPGRADE"):
            validate_relation_discrimination(mutated)

    def test_undeclared_alias_is_unverifiable_not_preserved(self) -> None:
        alias_policy = self.suite["policies"]["alias-global"]
        witness = next(
            witness
            for witness in self.suite["witnesses"]
            if witness["witness_id"] == "undeclared-alias"
        )
        result = evaluate_relation(alias_policy, witness["before"], witness["after"])
        self.assertEqual(result["outcome"], "UNVERIFIABLE")
        self.assertIn("undeclared-identity-alias", result["reason"])

    def test_unknown_policy_kind_fails_closed(self) -> None:
        policy = copy.deepcopy(self.suite["policies"]["strict-global"])
        policy["kind"] = "unknown-future-policy"
        witness = self.suite["witnesses"][0]
        result = evaluate_relation(policy, witness["before"], witness["after"])
        self.assertEqual(result["outcome"], "UNVERIFIABLE")
        self.assertIn("unsupported-policy-kind", result["reason"])

    def test_unknown_axis_policy_values_fail_closed(self) -> None:
        witness = self.suite["witnesses"][0]
        for field in (
            "identity_policy",
            "relation_type_policy",
            "multiplicity_policy",
            "direction_policy",
            "scope_policy",
        ):
            with self.subTest(field=field):
                policy = copy.deepcopy(self.suite["policies"]["strict-global"])
                policy[field] = "unknown-future-value"
                result = evaluate_relation(policy, witness["before"], witness["after"])
                self.assertEqual(result["outcome"], "UNVERIFIABLE")
                self.assertNotEqual(result["outcome"], "PRESERVED")

    def test_incomplete_global_scope_is_unverifiable(self) -> None:
        policy = self.suite["policies"]["strict-global"]
        witness = next(
            witness
            for witness in self.suite["witnesses"]
            if witness["witness_id"] == "incomplete-global-scope"
        )
        result = evaluate_relation(policy, witness["before"], witness["after"])
        self.assertEqual(result["outcome"], "UNVERIFIABLE")
        self.assertIn("incomplete-global-scope", result["reason"])

    def test_security_significant_mismatch_taxonomy(self) -> None:
        cases = {
            ("VIOLATED", "PRESERVED"): "UNSAFE_FALSE_PRESERVATION",
            ("UNVERIFIABLE", "PRESERVED"): "UNSAFE_UNVERIFIABLE_UPGRADE",
            ("PRESERVED", "VIOLATED"): "FALSE_VIOLATION",
            ("PRESERVED", "UNVERIFIABLE"): "PRESERVATION_NOT_ESTABLISHED",
            ("VIOLATED", "UNVERIFIABLE"): "VIOLATION_NOT_ESTABLISHED",
            ("UNVERIFIABLE", "VIOLATED"): "UNVERIFIABLE_MISCLASSIFIED_AS_VIOLATION",
            ("PRESERVED", "PRESERVED"): "MATCH",
        }
        for (expected, actual), classification in cases.items():
            with self.subTest(expected=expected, actual=actual):
                self.assertEqual(
                    classify_outcome_mismatch(expected, actual),
                    classification,
                )

    def test_cli_gate_reports_complete_separation_matrix(self) -> None:
        completed = subprocess.run(
            [sys.executable, "tools/validate_relation_discrimination.py"],
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
        for axis in REQUIRED_AXES:
            with self.subTest(axis=axis):
                self.assertIn(f"{axis}: SEPARATED", completed.stdout)
        self.assertIn("relation discrimination: PASS (5/5 axes; 8 witnesses)", completed.stdout)


if __name__ == "__main__":
    unittest.main()
