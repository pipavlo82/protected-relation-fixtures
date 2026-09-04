from __future__ import annotations

import json
from pathlib import Path
import shutil
import tempfile
import unittest

from tools.validate_external_evaluator_evidence import (
    EVIDENCE_ROOT,
    EvidenceValidationError,
    ROOT,
    validate_evidence,
)


class ExternalEvaluatorEvidenceTests(unittest.TestCase):
    def _copy(self, directory: str) -> Path:
        destination = Path(directory) / "v0"
        shutil.copytree(EVIDENCE_ROOT, destination)
        return destination

    def _write_json(self, path: Path, value: object) -> None:
        path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")

    def _must_fail(self, mutate) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self._copy(directory)
            mutate(root)
            with self.assertRaises(EvidenceValidationError):
                validate_evidence(root, repo_root=ROOT, check_git=False)

    def test_committed_evidence_is_valid(self) -> None:
        result = validate_evidence()
        self.assertEqual(result["inventory"]["total_files"], 211)
        self.assertEqual(result["inventory"]["total_bytes"], 1765722)
        self.assertEqual(len(result["matrix"]["models"]), 3)

    def test_changed_raw_output_is_detected(self) -> None:
        self._must_fail(
            lambda root: (root / "first-runs/llama3.1-8b/raw/prf-001.stdout.bin").write_bytes(
                (root / "first-runs/llama3.1-8b/raw/prf-001.stdout.bin").read_bytes() + b"x"
            )
        )

    def test_changed_request_is_detected(self) -> None:
        self._must_fail(
            lambda root: (root / "first-runs/qwen2.5-coder-7b/requests/prf-002.json").write_bytes(
                (root / "first-runs/qwen2.5-coder-7b/requests/prf-002.json").read_bytes() + b" "
            )
        )

    def test_changed_matrix_classification_is_detected(self) -> None:
        def mutate(root: Path) -> None:
            path = root / "first-run-matrix.json"
            value = json.loads(path.read_text(encoding="utf-8"))
            value["models"][0]["observations"][0]["mismatch_classification"] = "FALSE_VIOLATION"
            self._write_json(path, value)

        self._must_fail(mutate)

    def test_changed_model_identity_is_detected(self) -> None:
        def mutate(root: Path) -> None:
            path = root / "evidence-record.json"
            value = json.loads(path.read_text(encoding="utf-8"))
            value["experiments"][2]["model_identity"]["model_id"] = "wrong"
            self._write_json(path, value)

        self._must_fail(mutate)

    def test_changed_inventory_digest_is_detected(self) -> None:
        def mutate(root: Path) -> None:
            path = root / "evidence-record.json"
            value = json.loads(path.read_text(encoding="utf-8"))
            value["payload_inventory"]["sha256"] = "0" * 64
            self._write_json(path, value)

        self._must_fail(mutate)

    def test_deleted_bundle_is_detected(self) -> None:
        self._must_fail(lambda root: shutil.rmtree(root / "first-runs/qwen2.5-coder-7b"))

    def test_pre_repair_bundle_cannot_become_comparable(self) -> None:
        def mutate(root: Path) -> None:
            path = root / "first-run-matrix.json"
            value = json.loads(path.read_text(encoding="utf-8"))
            value["comparable_experiments"].insert(0, "qwen2.5-3b-pre-wrapper-repair")
            self._write_json(path, value)

        self._must_fail(mutate)

    def test_changed_frozen_v0_identity_is_detected(self) -> None:
        def mutate(root: Path) -> None:
            path = root / "evidence-record.json"
            value = json.loads(path.read_text(encoding="utf-8"))
            value["authority"]["frozen_v0_commit"] = "0" * 40
            self._write_json(path, value)

        self._must_fail(mutate)

    def test_unexpected_payload_file_is_detected(self) -> None:
        self._must_fail(lambda root: (root / "first-runs/llama3.1-8b/unexpected.txt").write_bytes(b"unexpected\n"))

    def test_duplicate_inventory_path_is_detected(self) -> None:
        def mutate(root: Path) -> None:
            path = root / "payload-inventory.json"
            value = json.loads(path.read_text(encoding="utf-8"))
            value["entries"].append(dict(value["entries"][0]))
            value["total_files"] += 1
            value["total_bytes"] += value["entries"][0]["byte_length"]
            self._write_json(path, value)

        self._must_fail(mutate)

    def test_noncanonical_inventory_order_is_detected(self) -> None:
        def mutate(root: Path) -> None:
            path = root / "payload-inventory.json"
            value = json.loads(path.read_text(encoding="utf-8"))
            value["entries"][0], value["entries"][1] = value["entries"][1], value["entries"][0]
            self._write_json(path, value)

        self._must_fail(mutate)


if __name__ == "__main__":
    unittest.main()
