from __future__ import annotations

import json
from pathlib import Path
import shutil
import tempfile
import unittest

from tools.validate_external_evaluator_repeated_evidence import (
    EVIDENCE_ROOT,
    ROOT,
    RepeatedEvidenceError,
    validate_repeated_evidence,
)


class ExternalEvaluatorRepeatedEvidenceTests(unittest.TestCase):
    def _copy(self, directory: str) -> Path:
        destination = Path(directory) / "repeated-runs"
        shutil.copytree(EVIDENCE_ROOT, destination)
        return destination

    def _write_json(self, path: Path, value: object) -> None:
        path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")

    def _mutate_json(self, path: Path, mutate) -> None:
        value = json.loads(path.read_text(encoding="utf-8"))
        mutate(value)
        self._write_json(path, value)

    def _must_fail(self, mutate) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self._copy(directory)
            mutate(root)
            with self.assertRaises(RepeatedEvidenceError):
                validate_repeated_evidence(root, repo_root=ROOT, check_git=False)

    def test_committed_repeated_evidence_is_valid(self) -> None:
        result = validate_repeated_evidence()
        self.assertEqual(result["matrix"]["overall"]["captured_observations"], 180)
        self.assertEqual(result["matrix"]["overall"]["valid_semantic_observations"], 177)
        self.assertEqual(result["matrix"]["overall"]["adapter_failures"], 3)

    def test_raw_stdout_mutation_is_killed(self) -> None:
        self._must_fail(lambda root: (root / "payload/qwen2.5-3b-instruct/prf-001/run-01/stdout.bin").write_bytes(b"mutated"))

    def test_request_mutation_is_killed(self) -> None:
        self._must_fail(lambda root: (root / "payload/qwen2.5-coder-7b/prf-002/run-01/request.json").write_bytes(b"{}\n"))

    def test_run_index_mutation_is_killed(self) -> None:
        self._must_fail(lambda root: self._mutate_json(root / "payload/qwen2.5-3b-instruct/prf-001/run-01/observation.json", lambda value: value.__setitem__("run_index", 2)))

    def test_semantic_outcome_mutation_is_killed(self) -> None:
        self._must_fail(lambda root: self._mutate_json(root / "payload/qwen2.5-3b-instruct/prf-001/run-01/observation.json", lambda value: value.__setitem__("semantic_outcome", "VIOLATED")))

    def test_benchmark_classification_mutation_is_killed(self) -> None:
        self._must_fail(lambda root: self._mutate_json(root / "repeated-run-matrix.json", lambda value: value["models"][0]["challenges"][0]["observations"][0].__setitem__("benchmark_classification", "MATCH")))

    def test_model_identity_mutation_is_killed(self) -> None:
        self._must_fail(lambda root: self._mutate_json(root / "payload/metadata/model-identities.json", lambda value: value["models"][0].__setitem__("model_id", "wrong")))

    def test_adapter_failure_cannot_become_unverifiable(self) -> None:
        def mutate(root: Path) -> None:
            path = root / "payload/llama3.1-8b/prf-002/run-07/observation.json"
            self._mutate_json(path, lambda value: (value.__setitem__("adapter_status", "RESPONSE_VALID"), value.__setitem__("semantic_outcome", "UNVERIFIABLE")))
        self._must_fail(mutate)

    def test_deleted_observation_is_killed(self) -> None:
        def mutate(root: Path) -> None:
            target = root / "payload/qwen2.5-3b-instruct/prf-004/run-04/observation.json"
            target.unlink()
        self._must_fail(mutate)

    def test_duplicate_observation_is_killed(self) -> None:
        def mutate(root: Path) -> None:
            source = root / "payload/qwen2.5-3b-instruct/prf-001/run-01"
            shutil.copytree(source, root / "payload/qwen2.5-3b-instruct/prf-001/run-11")
        self._must_fail(mutate)

    def test_old_first_run_cannot_enter_fresh_denominator(self) -> None:
        self._must_fail(lambda root: self._mutate_json(root / "repeated-run-matrix.json", lambda value: value["fresh_observation_policy"].__setitem__("historical_first_runs_counted_in_denominator", True)))

    def test_wrong_denominator_is_killed(self) -> None:
        self._must_fail(lambda root: self._mutate_json(root / "repeated-run-matrix.json", lambda value: value["models"][0]["challenges"][0].__setitem__("scheduled_observations", 11)))

    def test_stability_count_mutation_is_killed(self) -> None:
        self._must_fail(lambda root: self._mutate_json(root / "stability-summary.json", lambda value: value["models"][0]["challenges"][0]["outcome_counts"].__setitem__("PRESERVED", 8)))

    def test_unsafe_count_mutation_is_killed(self) -> None:
        self._must_fail(lambda root: self._mutate_json(root / "repeated-run-matrix.json", lambda value: value["overall"]["classification_counts"].__setitem__("UNSAFE_FALSE_PRESERVATION", 52)))

    def test_payload_inventory_mutation_is_killed(self) -> None:
        self._must_fail(lambda root: self._mutate_json(root / "payload-inventory.json", lambda value: value["entries"][0].__setitem__("sha256", "0" * 64)))

    def test_frozen_v0_identity_mutation_is_killed(self) -> None:
        self._must_fail(lambda root: self._mutate_json(root / "evidence-record.json", lambda value: value["authority"].__setitem__("frozen_v0_commit", "0" * 40)))

    def test_adapter_identity_mutation_is_killed(self) -> None:
        self._must_fail(lambda root: self._mutate_json(root / "evidence-record.json", lambda value: value["authority"].__setitem__("external_adapter_commit", "0" * 40)))

    def test_cross_model_summary_mutation_is_killed(self) -> None:
        self._must_fail(lambda root: self._mutate_json(root / "cross-model-summary.json", lambda value: value["repeated_security_significant_findings"].clear()))

    def test_report_aggregate_mutation_is_killed(self) -> None:
        def mutate(root: Path) -> None:
            path = root / "REPORT.md"
            path.write_text(path.read_text(encoding="utf-8").replace("177 valid semantic judgments", "176 valid semantic judgments", 1), encoding="utf-8", newline="\n")
        self._must_fail(mutate)

    def test_report_per_challenge_number_mutation_is_killed(self) -> None:
        def mutate(root: Path) -> None:
            path = root / "REPORT.md"
            path.write_text(path.read_text(encoding="utf-8").replace("| 9 / 1 / 0 |", "| 8 / 2 / 0 |", 1), encoding="utf-8", newline="\n")
        self._must_fail(mutate)


if __name__ == "__main__":
    unittest.main()
