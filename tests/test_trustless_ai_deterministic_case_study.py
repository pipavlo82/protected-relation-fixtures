from __future__ import annotations

import json
from pathlib import Path
import shutil
import tempfile
import unittest

from tools.validate_trustless_ai_deterministic_case_study import (
    AuditValidationError,
    LANE,
    ROOT,
    validate_audit,
)


class TrustlessAIDeterministicCaseStudyTests(unittest.TestCase):
    def _copy(self, directory: str) -> Path:
        destination = Path(directory) / "v0"
        shutil.copytree(LANE, destination)
        return destination

    def _load(self, root: Path, name: str) -> dict:
        return json.loads((root / name).read_text(encoding="utf-8"))

    def _write(self, root: Path, name: str, value: object) -> None:
        (root / name).write_text(
            json.dumps(value, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
            newline="\n",
        )

    def _case(self, value: dict, case_id: str) -> dict:
        return next(case for case in value["cases"] if case["case_id"] == case_id)

    def _must_fail(self, mutation) -> None:
        with tempfile.TemporaryDirectory() as directory:
            lane = self._copy(directory)
            mutation(lane)
            with self.assertRaises(AuditValidationError):
                validate_audit(lane, repo_root=ROOT, check_git=False)

    def test_committed_audit_is_valid(self) -> None:
        result = validate_audit()
        self.assertEqual(result["inventory"]["artifact_count"], 55)
        self.assertEqual(result["inventory"]["total_bytes"], 232259)
        self.assertEqual(len(result["cases"]["cases"]), 7)
        self.assertEqual(result["results"]["model_calls"], 0)

    def test_source_byte_mutation_is_killed(self) -> None:
        self._must_fail(lambda lane: (lane / "sources/recompute-kit/bin/recompute-storage-proof").write_bytes(
            (lane / "sources/recompute-kit/bin/recompute-storage-proof").read_bytes() + b"x"
        ))

    def test_source_commit_mutation_is_killed(self) -> None:
        def mutate(lane: Path) -> None:
            value = self._load(lane, "source-inventory.json")
            value["repositories"]["recompute-kit"]["commit"] = "0" * 40
            self._write(lane, "source-inventory.json", value)
        self._must_fail(mutate)

    def test_protected_relation_mutation_is_killed(self) -> None:
        def mutate(lane: Path) -> None:
            value = self._load(lane, "cases.json")
            self._case(value, "TAI-001")["protected_relation"] = "state_value_equality"
            self._write(lane, "cases.json", value)
        self._must_fail(mutate)

    def test_expected_outcome_mutation_is_killed(self) -> None:
        def mutate(lane: Path) -> None:
            value = self._load(lane, "cases.json")
            self._case(value, "TAI-005")["expected_outcome"] = "PRESERVED"
            self._write(lane, "cases.json", value)
        self._must_fail(mutate)

    def test_weak_observation_substitution_is_killed(self) -> None:
        def mutate(lane: Path) -> None:
            value = self._load(lane, "cases.json")
            case = self._case(value, "TAI-003")
            case["protected_relation"] = json.dumps(case["weak_observation"], sort_keys=True)
            self._write(lane, "cases.json", value)
        self._must_fail(mutate)

    def test_authority_scope_removal_is_killed(self) -> None:
        def mutate(lane: Path) -> None:
            value = self._load(lane, "cases.json")
            self._case(value, "TAI-004")["protected_scope"] = []
            self._write(lane, "cases.json", value)
        self._must_fail(mutate)

    def test_source_reference_removal_is_killed(self) -> None:
        def mutate(lane: Path) -> None:
            value = self._load(lane, "cases.json")
            self._case(value, "TAI-005")["source_refs"] = []
            self._write(lane, "cases.json", value)
        self._must_fail(mutate)

    def test_preservation_control_changed_to_violation_is_killed(self) -> None:
        def mutate(lane: Path) -> None:
            value = self._load(lane, "cases.json")
            self._case(value, "TAI-007")["expected_outcome"] = "VIOLATED"
            self._write(lane, "cases.json", value)
        self._must_fail(mutate)

    def test_live_failure_changed_to_verified_is_killed(self) -> None:
        def mutate(lane: Path) -> None:
            value = self._load(lane, "live-reproduction-summary.json")
            next(item for item in value["checks"] if item["check_id"] == "LIVE-004")["status"] = "LIVE_REPRODUCED"
            self._write(lane, "live-reproduction-summary.json", value)
        self._must_fail(mutate)

    def test_rpc_trusted_changed_to_rederived_is_killed(self) -> None:
        def mutate(lane: Path) -> None:
            value = self._load(lane, "cases.json")
            self._case(value, "TAI-001")["state_before"]["header_state_root_authority"] = "RE_DERIVED"
            self._write(lane, "cases.json", value)
        self._must_fail(mutate)

    def test_testnet_anchor_relabelled_stronger_is_killed(self) -> None:
        def mutate(lane: Path) -> None:
            value = self._load(lane, "cases.json")
            self._case(value, "TAI-002")["state_before"]["anchor_tier"] = "BITCOIN_POW_ANCHORED"
            self._write(lane, "cases.json", value)
        self._must_fail(mutate)

    def test_nested_bytes_relabelled_reproduced_is_killed(self) -> None:
        def mutate(lane: Path) -> None:
            value = self._load(lane, "cases.json")
            self._case(value, "TAI-006")["state_before"]["inner_semantics"] = "REPRODUCED"
            self._write(lane, "cases.json", value)
        self._must_fail(mutate)

    def test_profile_identity_binding_removal_is_killed(self) -> None:
        def mutate(lane: Path) -> None:
            value = self._load(lane, "cases.json")
            case = self._case(value, "TAI-003")
            case["state_after"]["profile_selected_repository"] = case["state_before"]["profile_selected_repository"]
            self._write(lane, "cases.json", value)
        self._must_fail(mutate)

    def test_exact_as_of_collapsed_to_current_value_is_killed(self) -> None:
        def mutate(lane: Path) -> None:
            value = self._load(lane, "cases.json")
            self._case(value, "TAI-004")["state_before"]["selector"] = "CURRENT_STATE"
            self._write(lane, "cases.json", value)
        self._must_fail(mutate)

    def test_source_inventory_digest_mutation_is_killed(self) -> None:
        def mutate(lane: Path) -> None:
            value = self._load(lane, "evidence-record.json")
            value["bindings"]["source_inventory_sha256"] = "0" * 64
            self._write(lane, "evidence-record.json", value)
        self._must_fail(mutate)


if __name__ == "__main__":
    unittest.main()
