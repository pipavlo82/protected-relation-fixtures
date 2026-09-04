from __future__ import annotations

import json
from pathlib import Path
import shutil
import tempfile
import unittest

from tools.validate_invinoveritas_epistemic_basis_v18 import (
    InvinoVeritasValidationError,
    LANE,
    ROOT,
    validate_case_study,
)


class InvinoVeritasEpistemicBasisV18Tests(unittest.TestCase):
    def _copy(self, directory: str) -> Path:
        destination = Path(directory) / "v18"
        shutil.copytree(LANE, destination)
        return destination

    def _load(self, lane: Path, name: str) -> dict:
        return json.loads((lane / name).read_text(encoding="utf-8"))

    def _write(self, lane: Path, name: str, value: object) -> None:
        (lane / name).write_text(
            json.dumps(value, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
            newline="\n",
        )

    def _must_fail(self, mutation) -> None:
        with tempfile.TemporaryDirectory() as directory:
            lane = self._copy(directory)
            mutation(lane)
            with self.assertRaises(InvinoVeritasValidationError):
                validate_case_study(lane, repo_root=ROOT, check_git=False)

    def test_committed_case_study_is_valid(self) -> None:
        result = validate_case_study()
        self.assertEqual(result["inventory"]["artifact_count"], 10)
        self.assertEqual(result["inventory"]["total_bytes"], 83231)
        self.assertEqual(result["results"]["result"]["classification"], "COMMITMENT_VIOLATION_DETECTED")

    def test_v17_absence_cannot_be_classified_evidence_against(self) -> None:
        def mutate(lane: Path) -> None:
            value = self._load(lane, "case-results.json")
            value["result"]["legacy_v17_control"]["epistemic_basis_interpretation"] = "evidence_against"
            self._write(lane, "case-results.json", value)
        self._must_fail(mutate)

    def test_v17_absence_cannot_be_classified_insufficient_evidence(self) -> None:
        def mutate(lane: Path) -> None:
            value = self._load(lane, "cases.json")
            value["cases"][0]["legacy_control"]["epistemic_basis_interpretation"] = "insufficient_evidence"
            self._write(lane, "cases.json", value)
        self._must_fail(mutate)

    def test_v18_preimage_must_name_epistemic_basis(self) -> None:
        def mutate(lane: Path) -> None:
            path = lane / "live/v18-original-retrieval.response.json"
            value = json.loads(path.read_bytes())
            payload = json.loads(value["event"]["content"])
            payload["decision_ref_preimage_fields"].remove("epistemic_basis")
            value["event"]["content"] = json.dumps(payload, separators=(",", ":"))
            path.write_text(json.dumps(value, separators=(",", ":")), encoding="utf-8", newline="")
        self._must_fail(mutate)

    def test_original_and_tampered_results_cannot_converge(self) -> None:
        def mutate(lane: Path) -> None:
            value = self._load(lane, "case-results.json")
            value["result"]["v18_tamper"]["decision_ref_recomputes"] = True
            self._write(lane, "case-results.json", value)
        self._must_fail(mutate)

    def test_tamper_cannot_be_recast_as_reviewer_verdict_change(self) -> None:
        def mutate(lane: Path) -> None:
            value = self._load(lane, "case-results.json")
            value["result"]["underlying_reviewer_verdict_changed"] = True
            self._write(lane, "case-results.json", value)
        self._must_fail(mutate)

    def test_legacy_v17_cannot_be_reclassified_as_failed_v18(self) -> None:
        def mutate(lane: Path) -> None:
            value = self._load(lane, "case-results.json")
            value["result"]["legacy_v17_control"]["classification"] = "FAILED_V18_CASE"
            self._write(lane, "case-results.json", value)
        self._must_fail(mutate)

    def test_raw_tamper_response_mutation_is_killed(self) -> None:
        self._must_fail(lambda lane: (lane / "live/v18-tampered-verify.response.json").write_bytes(
            (lane / "live/v18-tampered-verify.response.json").read_bytes() + b" "
        ))

    def test_inventory_digest_mutation_is_killed(self) -> None:
        def mutate(lane: Path) -> None:
            value = self._load(lane, "evidence-record.json")
            value["artifact_inventory"]["sha256"] = "0" * 64
            self._write(lane, "evidence-record.json", value)
        self._must_fail(mutate)

    def test_upstream_report_cannot_be_upgraded_to_verified(self) -> None:
        def mutate(lane: Path) -> None:
            value = self._load(lane, "upstream-report.json")
            value["resolution"]["status"] = "INDEPENDENTLY_VERIFIED"
            self._write(lane, "upstream-report.json", value)
        self._must_fail(mutate)

    def test_approximate_offline_recomputation_cannot_be_claimed(self) -> None:
        def mutate(lane: Path) -> None:
            value = self._load(lane, "live-reproduction-summary.json")
            value["offline_decision_ref_recomputation"]["status"] = "VERIFIED"
            self._write(lane, "live-reproduction-summary.json", value)
        self._must_fail(mutate)


if __name__ == "__main__":
    unittest.main()
