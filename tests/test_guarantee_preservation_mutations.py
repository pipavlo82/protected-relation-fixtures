from __future__ import annotations

from pathlib import Path
import textwrap
import unittest

from tools.guarantee_preservation_mutations import Mutation, Replacement, run_mutation


TOY_SOURCE = textwrap.dedent('''
    # baseline marker
    def evaluate(name):
        if name == "adverse":
            outcome = "UNVERIFIABLE"
        else:
            outcome = "PRESERVED"
        return {
            "schema_version": "guarantee-preservation-v0",
            "context": None,
            "policy_digest": "sha256:" + "0" * 64,
            "observation_bindings": {
                "adapter_ref": None, "evaluator_ref": None,
                "context": None, "dependency_basis": None,
            },
            "envelope_digest": None,
            "evidence_digests": [],
            "policy_id": "bounded-toy",
            "outcome": outcome,
            "reason": "bounded_control",
            "guarantee": "bounded-guarantee" if outcome == "PRESERVED" else None,
            "native": {"grade": "NATIVE_PASS"},
            "checks": [],
            "establishes": ["bounded-guarantee"] if outcome == "PRESERVED" else [],
            "does_not_establish": ["global_soundness"],
        }
''')
EXPECTATIONS = {
    "positive": {"outcome": "PRESERVED", "native": {"grade": "NATIVE_PASS"}},
    "adverse": {"outcome": "UNVERIFIABLE", "native": {"grade": "NATIVE_PASS"}},
}


class MutationHarnessIntegrityTests(unittest.TestCase):
    def run_replacement(self, old, new, *, source=TOY_SOURCE, runner=None, expectations=None):
        mutation = Mutation(
            "toy-guard", "tools/guarantee_preservation.py",
            (Replacement(old, new),), "adverse", "positive",
        )
        return run_mutation(
            mutation,
            source_text=source,
            probe_runner=runner or (lambda namespace, name: namespace["evaluate"](name)),
            expectations=EXPECTATIONS if expectations is None else expectations,
        )

    def test_kill_requires_named_adverse_failure_and_unaffected_positive(self) -> None:
        report = self.run_replacement('if name == "adverse":', "if False:")
        self.assertEqual(report["status"], "KILLED")
        self.assertEqual(report["adverse_test"], "adverse")
        self.assertEqual(report["positive_control"], "positive")
        observations = report["observations"]["mutant"]
        self.assertTrue(observations["positive"]["matched"])
        self.assertFalse(observations["adverse"]["matched"])
        self.assertNotEqual(report["source_sha256"], report["mutated_sha256"])

    def test_unapplied_ambiguous_and_unchanged_replacements_are_not_kills(self) -> None:
        for old, new in (
            ("missing guard", "replacement"),
            ("outcome", "renamed"),
            ('if name == "adverse":', 'if name == "adverse":'),
        ):
            with self.subTest(old=old):
                self.assertEqual(self.run_replacement(old, new)["status"], "UNAPPLIED")

    def test_compile_errors_are_not_kills(self) -> None:
        report = self.run_replacement('if name == "adverse":', "if ???:")
        self.assertEqual(report["status"], "COMPILE_ERROR")

    def test_module_and_adverse_probe_crashes_are_not_kills(self) -> None:
        for old, new in (
            ("# baseline marker", 'raise RuntimeError("module failed")'),
            ('outcome = "UNVERIFIABLE"', 'raise RuntimeError("adverse failed")'),
        ):
            with self.subTest(phase=old):
                self.assertEqual(self.run_replacement(old, new)["status"], "CRASHED")

    def test_invalid_output_cannot_count_as_adverse_test_failure(self) -> None:
        old = 'outcome = "UNVERIFIABLE"'
        for new in ("return None", 'return {"outcome": "PRESERVED"}', "outcome = []"):
            with self.subTest(new=new):
                self.assertEqual(self.run_replacement(old, new)["status"], "INVALID_OUTPUT")
        from tools.guarantee_preservation_mutations import DECISION_KEYS

        actions = [("remove", field, None) for field in sorted(DECISION_KEYS)] + [
            ("set", "unexpected", True),
            ("set", "context", "unsupported"),
            ("set", "policy_digest", "not-a-digest"),
            ("set", "observation_bindings", []),
            ("set", "envelope_digest", 42),
            ("set", "evidence_digests", [{"ref": "r", "digest": "not-a-digest"}]),
        ]
        for action, field, value in actions:
            def changed_shape(namespace, name, *, action=action, field=field, value=value):
                decision = namespace["evaluate"](name)
                if namespace.get("shape_mutant") and name == "adverse":
                    if action == "remove":
                        del decision[field]
                    else:
                        decision[field] = value
                return decision

            with self.subTest(action=action, field=field):
                report = self.run_replacement(
                    "# baseline marker", "shape_mutant = True", runner=changed_shape,
                )
                self.assertEqual(report["status"], "INVALID_OUTPUT")

    def test_positive_control_damage_is_not_a_kill(self) -> None:
        report = self.run_replacement('if name == "adverse":', "if True:")
        self.assertEqual(report["status"], "POSITIVE_CONTROL_FAILED")

    def test_semantically_unchanged_applied_mutant_survives(self) -> None:
        report = self.run_replacement("# baseline marker", "# changed marker")
        self.assertEqual(report["status"], "SURVIVED")

    def test_failed_baseline_cannot_inflate_kills(self) -> None:
        source = TOY_SOURCE.replace('outcome = "PRESERVED"', 'outcome = "VIOLATED"')
        report = self.run_replacement('if name == "adverse":', "if False:", source=source)
        self.assertEqual(report["status"], "BASELINE_FAILED")

    def test_explanation_change_alone_is_not_a_semantic_kill(self) -> None:
        report = self.run_replacement('"reason": "bounded_control"', '"reason": "different_detail"')
        self.assertEqual(report["status"], "SURVIVED")

    def test_invalid_probe_spec_is_not_a_kill(self) -> None:
        mutation = Mutation(
            "missing-positive", "tools/guarantee_preservation.py",
            (Replacement('if name == "adverse":', "if False:"),), "adverse", "adverse",
        )
        report = run_mutation(
            mutation, source_text=TOY_SOURCE,
            probe_runner=lambda namespace, name: namespace["evaluate"](name),
            expectations=EXPECTATIONS,
        )
        self.assertEqual(report["status"], "INVALID_SPEC")

    def test_compilation_does_not_rewrite_named_repository_source(self) -> None:
        source_path = Path(__file__).resolve().parents[1] / "tools/guarantee_preservation.py"
        before = source_path.read_bytes()
        self.run_replacement('if name == "adverse":', "if False:")
        self.assertEqual(source_path.read_bytes(), before)



class GuaranteePreservationMutationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        from tools.guarantee_preservation import consume
        from tools.guarantee_preservation_mutations import prepare_probes, probe_expectations

        cls.namespace = {"consume": consume}
        cls.probes = prepare_probes()
        cls.expectations = probe_expectations(cls.probes)

    def check_named_probe(self, name):
        from tools.guarantee_preservation_mutations import execute_probe

        decision = execute_probe(self.namespace, name, probes=self.probes)
        for key, expected in self.expectations[name].items():
            with self.subTest(probe=name, dimension=key):
                self.assertEqual(decision[key], expected)
        return decision

    def test_prf_positive_control(self) -> None:
        self.check_named_probe("test_prf_positive_control")

    def test_kit_positive_control(self) -> None:
        decision = self.check_named_probe("test_kit_positive_control")
        self.assertEqual(decision["native"]["signature_predicate"], "TRUE")
        self.assertEqual(decision["native"]["evidence_grade"]["value"], "AUTHENTICATED_REPORT")

    def test_context_binding_mismatch(self) -> None:
        envelope, policy, basis, _ = self.probes["test_context_binding_mismatch"]
        self.assertNotEqual(envelope["context"], policy["context"])
        self.assertEqual(basis["context"], policy["context"])
        self.check_named_probe("test_context_binding_mismatch")

    def test_empty_dependencies_fail_closed(self) -> None:
        envelope, _, basis, _ = self.probes["test_empty_dependencies_fail_closed"]
        self.assertEqual(envelope["depends_on"], [])
        self.assertEqual(envelope["checks"], [])
        self.assertTrue(basis["mandatory"])
        self.check_named_probe("test_empty_dependencies_fail_closed")

    def test_unaccepted_dependency_basis(self) -> None:
        _, _, basis, _ = self.probes["test_unaccepted_dependency_basis"]
        self.assertEqual(basis["acceptance"]["status"], "DECLARED_ONLY")
        self.check_named_probe("test_unaccepted_dependency_basis")

    def test_conflicting_evidence(self) -> None:
        envelope, _, _, _ = self.probes["test_conflicting_evidence"]
        witnesses = [
            check["outcome"] for check in envelope["checks"]
            if check["dependency_id"] == "award_settlement_relation"
        ]
        self.assertEqual(set(witnesses), {"TRUE", "FALSE"})
        self.check_named_probe("test_conflicting_evidence")

    def test_native_grade_is_not_transfer_verdict(self) -> None:
        decision = self.check_named_probe("test_native_grade_is_not_transfer_verdict")
        self.assertEqual(decision["native"]["signature_predicate"], "FALSE")
        self.assertEqual(decision["native"]["evidence_grade"]["value"], "AUTHENTICATED_REPORT")
        self.assertEqual(decision["outcome"], "VIOLATED")

    def test_dependency_digest_binding(self) -> None:
        from tools.guarantee_preservation import digest

        envelope, _, _, _ = self.probes["test_dependency_digest_binding"]
        self.assertNotEqual(envelope["depends_on_digest"], digest(envelope["depends_on"]))
        self.check_named_probe("test_dependency_digest_binding")

    def test_omitted_required_relation_fail_closed(self) -> None:
        envelope, _, basis, _ = self.probes["test_omitted_required_relation_fail_closed"]
        self.assertIn("award_settlement_relation", basis["mandatory"])
        self.assertNotIn("award_settlement_relation", envelope["depends_on"])
        self.assertEqual(envelope["native"]["output"]["outcome"], "VIOLATED")
        self.check_named_probe("test_omitted_required_relation_fail_closed")

    def test_all_required_source_mutants_are_killed_with_unaffected_positives(self) -> None:
        from tools.guarantee_preservation_mutations import validate_mutations

        source_path = Path(__file__).resolve().parents[1] / "tools/guarantee_preservation.py"
        before = source_path.read_bytes()
        report = validate_mutations()
        self.assertEqual(report["status"], "PASS")
        self.assertEqual(report["required_mutants"], 7)
        self.assertEqual(report["killed"], 7)
        self.assertEqual(report["not_killed"], 0)
        self.assertEqual(len(report["mutants"]), 7)
        self.assertEqual({record["id"] for record in report["mutants"]}, {
            "context-binding-bypass", "vacuous-empty-dependencies",
            "unaccepted-basis-acceptance", "conflicting-witnesses-ignored",
            "native-grade-shortcuts-transfer", "dependency-digest-bypass",
            "omitted-required-false-relation",
        })
        for record in report["mutants"]:
            with self.subTest(mutation=record["id"]):
                self.assertEqual(record["source_path"], "tools/guarantee_preservation.py")
                self.assertEqual(record["status"], "KILLED")
                self.assertNotEqual(record["source_sha256"], record["mutated_sha256"])
                for observation in record["observations"]["baseline"].values():
                    self.assertEqual(observation["state"], "VALID")
                    self.assertTrue(observation["matched"])
                mutant = record["observations"]["mutant"]
                self.assertEqual(mutant[record["positive_control"]]["state"], "VALID")
                self.assertTrue(mutant[record["positive_control"]]["matched"])
                self.assertEqual(mutant[record["adverse_test"]]["state"], "VALID")
                self.assertFalse(mutant[record["adverse_test"]]["matched"])
                self.assertEqual(mutant[record["adverse_test"]]["outcome"], "PRESERVED")
        self.assertEqual(source_path.read_bytes(), before)

    def test_missing_required_mutant_cannot_make_partial_suite_pass(self) -> None:
        from unittest.mock import patch
        import tools.guarantee_preservation_mutations as harness

        with patch.object(harness, "MUTATIONS", harness.MUTATIONS[:-1]):
            with self.assertRaises(harness.MutationValidationError):
                harness.run_mutations()

    def test_mutation_cli_reports_each_named_kill(self) -> None:
        import json
        import subprocess
        import sys

        root = Path(__file__).resolve().parents[1]
        completed = subprocess.run(
            [sys.executable, *(["-O"] if sys.flags.optimize else []), "-B",
             "tools/guarantee_preservation_mutations.py"],
            cwd=root, capture_output=True, text=True, timeout=60, check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        report = json.loads(completed.stdout)
        self.assertEqual((report["status"], report["killed"], report["not_killed"]), ("PASS", 7, 0))


if __name__ == "__main__":
    unittest.main()
