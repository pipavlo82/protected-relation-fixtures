from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path

from tools.validate_codex_gpt56_repeated_evidence import (
    EvidenceValidationError,
    LANE,
    validate,
)


class CodexGpt56RepeatedEvidenceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name) / "lane"
        shutil.copytree(LANE, self.root)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def mutate_json(self, relative_path: str, mutate) -> None:
        path = self.root / relative_path
        value = json.loads(path.read_text(encoding="utf-8"))
        mutate(value)
        path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")

    def rejected(self) -> None:
        with self.assertRaises(EvidenceValidationError):
            validate(self.root, check_git=False)

    def test_canonical_evidence_validates(self) -> None:
        result = validate(self.root, check_git=False)
        self.assertEqual(result["observations"], 60)
        self.assertEqual(result["match"], 50)
        self.assertEqual(result["unsafe_unverifiable_upgrade"], 10)

    def test_raw_output_mutation_is_killed(self) -> None:
        path = self.root / "payload/isolated/prf-001/run-01/raw-final-response.bin"
        path.write_bytes(path.read_bytes() + b" ")
        self.rejected()

    def test_request_mutation_is_killed(self) -> None:
        path = self.root / "payload/isolated/prf-001/run-01/request.json"
        path.write_bytes(path.read_bytes() + b" ")
        self.rejected()

    def test_prompt_mutation_is_killed(self) -> None:
        path = self.root / "payload/isolated/prf-001/run-01/prompt.txt"
        path.write_bytes(path.read_bytes() + b"changed\n")
        self.rejected()

    def test_duplicate_run_index_is_killed(self) -> None:
        self.mutate_json("payload/isolated/prf-001/run-02/observation.json", lambda value: value.__setitem__("run_index", 1))
        self.rejected()

    def test_removed_observation_is_killed(self) -> None:
        (self.root / "payload/isolated/prf-001/run-01/observation.json").unlink()
        self.rejected()

    def test_semantic_outcome_mutation_is_killed(self) -> None:
        self.mutate_json("payload/isolated/prf-001/run-01/observation.json", lambda value: value["semantic_payload"].__setitem__("outcome", "PRESERVED"))
        self.rejected()

    def test_classification_mutation_is_killed(self) -> None:
        self.mutate_json("repeated-run-matrix.json", lambda value: value["challenges"][0]["observations"][0].__setitem__("benchmark_classification", "UNSAFE_FALSE_PRESERVATION"))
        self.rejected()

    def test_model_identity_mutation_is_killed(self) -> None:
        self.mutate_json("payload/isolated/prf-001/run-01/observation.json", lambda value: value.__setitem__("model", "different-model"))
        self.rejected()

    def test_reasoning_identity_mutation_is_killed(self) -> None:
        self.mutate_json("payload/isolated/prf-001/run-01/observation.json", lambda value: value.__setitem__("reasoning_effort", "low"))
        self.rejected()

    def test_oracle_marker_in_evaluator_input_is_killed(self) -> None:
        path = self.root / "payload/isolated/prf-001/run-01/prompt.txt"
        path.write_bytes(path.read_bytes() + b'\n{"oracle":"answer"}\n')
        self.rejected()

    def test_prior_model_result_in_evaluator_input_is_killed(self) -> None:
        path = self.root / "payload/isolated/prf-001/run-01/prompt.txt"
        path.write_bytes(path.read_bytes() + b"\nqwen2.5 prior result\n")
        self.rejected()

    def test_child_cwd_changed_to_prf_repository_is_killed(self) -> None:
        self.mutate_json("payload/isolated/prf-001/run-01/observation.json", lambda value: value.__setitem__("isolated_cwd", r"C:\repo\protected-relation-fixtures"))
        self.rejected()

    def test_capture_scoring_order_mutation_is_killed(self) -> None:
        self.mutate_json("payload/scoring/scoring-phase.json", lambda value: value.__setitem__("capture_was_closed_before_oracle_load", False))
        self.rejected()

    def test_adapter_failure_upgraded_to_unverifiable_is_killed(self) -> None:
        def mutate(value):
            value["adapter_status"] = "INVALID_EVALUATOR_OUTPUT"
            value["semantic_payload"] = {"outcome": "UNVERIFIABLE", "reason_detail": "fabricated"}

        self.mutate_json("payload/isolated/prf-001/run-01/observation.json", mutate)
        self.rejected()

    def test_stability_metric_mutation_is_killed(self) -> None:
        self.mutate_json("stability-summary.json", lambda value: value["challenges"][0]["modal_outcome_share"].__setitem__("numerator", 9))
        self.rejected()

    def test_denominator_mutation_is_killed(self) -> None:
        self.mutate_json("repeated-run-matrix.json", lambda value: value["challenges"][0].__setitem__("scheduled_observations", 9))
        self.rejected()

    def test_comparison_summary_mutation_is_killed(self) -> None:
        self.mutate_json("cross-model-comparison.json", lambda value: value["codex"]["classification_counts"].__setitem__("MATCH", 49))
        self.rejected()

    def test_frozen_v0_identity_mutation_is_killed(self) -> None:
        self.mutate_json("evidence-record.json", lambda value: value["authority"].__setitem__("frozen_v0_commit", "0" * 40))
        self.rejected()


if __name__ == "__main__":
    unittest.main()
