from __future__ import annotations

import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

from adapters.v0.contract import (
    AdapterContractViolation,
    CHALLENGE_ROOT,
    bind_evaluator_output,
    build_request,
    digest_value,
    invocation_context_for,
    run_command_adapter,
    validate_evaluator_output,
    validate_request,
    validate_response,
)
from adapters.v0.reference_adapter import evaluate
from adapters.v0.score_results import classify, score_results


ROOT = Path(__file__).resolve().parents[1]
CONFIG_DIGEST = "0" * 64
V0_COMMIT = "98ccba804c725777e155ad2f1a07bae49754376b"
V0_TREE = "c2449cb3a52e60c4f93e3c8a3a35c086c47f2d63"
V0_INVENTORY_SHA256 = "d29597ea7005c9aac31cfd50cca915d84cb0b203a18564fe654217d7733ded55"


class ExternalAdapterContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.requests = [
            build_request(
                path,
                evaluator_id="reference-prf-v0",
                evaluator_version="1",
                config_digest=CONFIG_DIGEST,
            )
            for path in sorted(CHALLENGE_ROOT.glob("prf-*.json"))
        ]
        cls.request_by_id = {request["challenge_id"]: request for request in cls.requests}

    def _context(self, request: dict[str, object]) -> dict[str, object]:
        return invocation_context_for(
            request,
            ["test-evaluator", request["challenge_id"]],
            metadata={"invocation_id": f"test-{request['challenge_id']}"},
        )

    def _semantic(self, outcome: str, detail: str = "Evaluator explanation.") -> dict[str, str]:
        return {"outcome": outcome, "reason_detail": detail}

    def _response(self, challenge_id: str = "prf-001") -> dict[str, object]:
        request = self.request_by_id[challenge_id]
        return bind_evaluator_output(request, evaluate(request), self._context(request))

    def _run_python(self, request: dict[str, object], source: str, timeout: float = 5.0) -> dict[str, object]:
        return run_command_adapter(
            request,
            [sys.executable, "-c", source],
            timeout_seconds=timeout,
            recorded_at="2026-09-04T00:00:00+00:00",
            invocation_metadata={"invocation_id": f"test-{request['challenge_id']}"},
        )

    def _run_output(self, request: dict[str, object], output: object) -> dict[str, object]:
        source = f"import json; print(json.dumps({output!r}))"
        return self._run_python(request, source)

    def _reference_transcripts(self) -> list[dict[str, object]]:
        adapter = str(ROOT / "adapters" / "v0" / "reference_adapter.py")
        return [
            run_command_adapter(
                request,
                [sys.executable, adapter],
                timeout_seconds=5.0,
                recorded_at="2026-09-04T00:00:00+00:00",
                invocation_metadata={"invocation_id": f"reference-{request['challenge_id']}"},
            )
            for request in self.requests
        ]

    def test_reference_adapter_blind_run_scores_all_six_matches(self) -> None:
        transcripts = self._reference_transcripts()
        self.assertEqual([row["adapter_status"] for row in transcripts], ["RESPONSE_VALID"] * 6)
        report = score_results(self.requests, transcripts)
        self.assertEqual(report["semantic_responses"], 6)
        self.assertEqual(report["classifications"]["MATCH"], 6)
        self.assertEqual(sum(report["classifications"].values()), 6)
        self.assertEqual(report["classifications"]["UNSAFE_FALSE_PRESERVATION"], 0)
        self.assertEqual(report["adapter_failures"], {})

    def test_reference_adapter_emits_only_minimal_semantic_payload(self) -> None:
        for request in self.requests:
            with self.subTest(challenge_id=request["challenge_id"]):
                self.assertEqual(set(evaluate(request)), {"outcome", "reason_detail"})

    def test_reference_adapter_source_does_not_read_scorer_or_oracle(self) -> None:
        source = (ROOT / "adapters/v0/reference_adapter.py").read_text(encoding="utf-8").lower()
        self.assertNotIn("oracle", source)
        self.assertNotIn("score_results", source)

    def test_requests_exclude_fixture_class_and_answer_fields(self) -> None:
        serialized = json.dumps(self.requests, sort_keys=True)
        self.assertNotIn('"class"', serialized)
        self.assertNotIn('"expected"', serialized)
        self.assertNotIn('"oracle"', serialized)
        self.assertNotIn("UNSAFE_FALSE_PRESERVATION", serialized)
        self.assertNotIn("UNSAFE_UNVERIFIABLE_UPGRADE", serialized)

    def test_evaluator_output_schema_exposes_no_benchmark_owned_fields(self) -> None:
        schema = json.loads((ROOT / "adapters/v0/evaluator-output-schema.json").read_text(encoding="utf-8"))
        self.assertEqual(set(schema["properties"]), {"outcome", "reason_detail"})
        self.assertEqual(set(schema["required"]), {"outcome", "reason_detail"})

    def test_request_with_expected_field_is_rejected(self) -> None:
        request = dict(self.requests[0])
        request["expected"] = "VIOLATED"
        with self.assertRaises(AdapterContractViolation):
            validate_request(request)

    def test_request_with_nested_oracle_derived_label_is_rejected(self) -> None:
        request = json.loads(json.dumps(self.requests[0]))
        request["execution_metadata"] = {"invocation_id": "oracle says violated"}
        with self.assertRaisesRegex(AdapterContractViolation, "ORACLE_LEAKAGE"):
            validate_request(request)

    def test_copied_fixture_metadata_is_rejected_by_builder(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "prf-001.json"
            challenge = json.loads((CHALLENGE_ROOT / "prf-001.json").read_text(encoding="utf-8"))
            challenge["metadata"] = {"expected": "VIOLATED"}
            path.write_text(json.dumps(challenge, indent=2) + "\n", encoding="utf-8", newline="\n")
            with self.assertRaisesRegex(AdapterContractViolation, "CHALLENGE_FIELD_SET_MISMATCH"):
                build_request(
                    path,
                    evaluator_id="reference-prf-v0",
                    evaluator_version="1",
                    config_digest=CONFIG_DIGEST,
                )

    def test_challenge_identifier_cannot_embed_answer_class(self) -> None:
        request = dict(self.requests[0])
        request["challenge_id"] = "prf-violated-001"
        with self.assertRaises(AdapterContractViolation):
            validate_request(request)

    def test_profile_bytes_are_bound_by_digest(self) -> None:
        request = json.loads(json.dumps(self.requests[0]))
        request["protected_relation_profile"]["identity_policy"] = "substituted"
        with self.assertRaisesRegex(AdapterContractViolation, "PROTECTED_RELATION_PROFILE_DIGEST_MISMATCH"):
            validate_request(request)

    def test_valid_violated_minimal_output_becomes_bound_envelope(self) -> None:
        transcript = self._run_output(self.requests[0], self._semantic("VIOLATED"))
        self.assertEqual(transcript["adapter_status"], "RESPONSE_VALID")
        self.assertEqual(transcript["normalized_response"]["outcome"], "VIOLATED")

    def test_valid_preserved_minimal_output_becomes_bound_envelope(self) -> None:
        transcript = self._run_output(self.requests[0], self._semantic("PRESERVED"))
        self.assertEqual(transcript["adapter_status"], "RESPONSE_VALID")
        self.assertEqual(transcript["normalized_response"]["outcome"], "PRESERVED")

    def test_valid_unverifiable_is_semantic_outcome_not_adapter_failure(self) -> None:
        transcript = self._run_output(self.requests[0], self._semantic("UNVERIFIABLE", "Insufficient facts."))
        self.assertEqual(transcript["adapter_status"], "RESPONSE_VALID")
        self.assertEqual(transcript["evaluator_output"]["outcome"], "UNVERIFIABLE")
        self.assertEqual(transcript["normalized_response"]["outcome"], "UNVERIFIABLE")

    def test_wrapper_copies_exact_request_challenge_and_profile_digests(self) -> None:
        request = self.requests[0]
        response = bind_evaluator_output(request, self._semantic("VIOLATED"), self._context(request))
        self.assertEqual(response["challenge_digest"], request["challenge_digest"])
        self.assertEqual(
            response["protected_relation_profile_digest"],
            request["protected_relation_profile_digest"],
        )
        self.assertEqual(response["request_digest"], digest_value(request))

    def test_model_supplies_no_digest_or_identity_fields(self) -> None:
        output = evaluate(self.requests[0])
        forbidden = {"challenge_digest", "protected_relation_profile_digest", "request_digest", "evaluator"}
        self.assertTrue(forbidden.isdisjoint(output))

    def test_model_provided_fake_digest_is_rejected_as_undeclared(self) -> None:
        output = self._semantic("VIOLATED")
        output["challenge_digest"] = "f" * 64
        with self.assertRaisesRegex(AdapterContractViolation, "evaluator output schema violation"):
            validate_evaluator_output(output)

    def test_non_string_reason_detail_is_protocol_failure(self) -> None:
        transcript = self._run_output(self.requests[0], {"outcome": "VIOLATED", "reason_detail": None})
        self.assertEqual(transcript["adapter_status"], "INVALID_EVALUATOR_OUTPUT")
        self.assertIsNone(transcript["normalized_response"])

    def test_unknown_outcome_is_protocol_failure(self) -> None:
        transcript = self._run_output(self.requests[0], self._semantic("UNKNOWN"))
        self.assertEqual(transcript["adapter_status"], "INVALID_EVALUATOR_OUTPUT")
        self.assertIsNone(transcript["normalized_response"])

    def test_benchmark_mismatch_class_cannot_be_semantic_outcome(self) -> None:
        transcript = self._run_output(self.requests[0], self._semantic("UNSAFE_FALSE_PRESERVATION"))
        self.assertEqual(transcript["adapter_status"], "INVALID_EVALUATOR_OUTPUT")
        self.assertIsNone(transcript["normalized_response"])

    def test_malformed_json_is_adapter_failure_not_semantic_outcome(self) -> None:
        transcript = self._run_python(self.requests[0], "print('not-json')")
        self.assertEqual(transcript["adapter_status"], "MALFORMED_RESPONSE")
        self.assertIsNone(transcript["evaluator_output"])

    def test_nonzero_exit_is_adapter_failure_not_preserved(self) -> None:
        transcript = self._run_python(self.requests[0], "raise RuntimeError('boom')")
        self.assertEqual(transcript["adapter_status"], "PROCESS_ERROR")
        self.assertIsNone(transcript["evaluator_output"])

    def test_timeout_is_adapter_failure_not_preserved(self) -> None:
        transcript = self._run_python(self.requests[0], "import time; time.sleep(2)", timeout=0.05)
        self.assertEqual(transcript["adapter_status"], "TIMEOUT")
        self.assertIsNone(transcript["evaluator_output"])

    def test_empty_response_is_adapter_failure_not_preserved(self) -> None:
        transcript = self._run_python(self.requests[0], "pass")
        self.assertEqual(transcript["adapter_status"], "EMPTY_RESPONSE")
        self.assertIsNone(transcript["evaluator_output"])

    def test_unsupported_challenge_cannot_be_upgraded_to_preserved(self) -> None:
        request = json.loads(json.dumps(self.requests[0]))
        request["challenge_id"] = "prf-999"
        context = self._context(request)
        with self.assertRaisesRegex(AdapterContractViolation, "UNSUPPORTED_CHALLENGE_UPGRADED"):
            bind_evaluator_output(request, self._semantic("PRESERVED"), context)
        unsupported = evaluate(request)
        self.assertEqual(unsupported["outcome"], "UNVERIFIABLE")
        response = bind_evaluator_output(request, unsupported, context)
        self.assertEqual(response["outcome"], "UNVERIFIABLE")

    def test_scorer_rejects_noncanonical_oracle_identity(self) -> None:
        transcripts = self._reference_transcripts()
        with tempfile.TemporaryDirectory() as directory:
            oracle = Path(directory) / "expected-results.json"
            shutil.copyfile(ROOT / "corpus/v0/oracle/expected-results.json", oracle)
            oracle.write_bytes(oracle.read_bytes().replace(b"VIOLATED", b"PRESERVED", 1))
            with self.assertRaisesRegex(AdapterContractViolation, "ORACLE_IDENTITY_MISMATCH"):
                score_results(self.requests, transcripts, oracle_path=oracle)

    def test_non_v0_challenge_bytes_cannot_claim_v0_digest(self) -> None:
        original = CHALLENGE_ROOT / "prf-001.json"
        claimed = hashlib.sha256(original.read_bytes()).hexdigest()
        with tempfile.TemporaryDirectory() as directory:
            changed = Path(directory) / "prf-001.json"
            changed_bytes = original.read_bytes()[:-1] + b" \n"
            self.assertNotEqual(changed_bytes, original.read_bytes())
            changed.write_bytes(changed_bytes)
            with self.assertRaisesRegex(AdapterContractViolation, "CHALLENGE_DIGEST_CLAIM_MISMATCH"):
                build_request(
                    changed,
                    evaluator_id="reference-prf-v0",
                    evaluator_version="1",
                    config_digest=CONFIG_DIGEST,
                    claimed_challenge_digest=claimed,
                )

    def test_scorer_rejects_request_payload_not_matching_frozen_challenge(self) -> None:
        request = json.loads(json.dumps(self.requests[0]))
        request["evaluation_input"]["after"]["A"] = ["B", "C", "D", "E", "F", "G"]
        transcript = self._run_python(request, "raise RuntimeError('not reached')")
        with self.assertRaisesRegex(AdapterContractViolation, "REQUEST_EVALUATION_INPUT_MISMATCH"):
            score_results([request], [transcript])

    def test_captured_output_cannot_be_replayed_against_different_request(self) -> None:
        request0 = self.request_by_id["prf-001"]
        request1 = self.request_by_id["prf-002"]
        captured_output = self._semantic("VIOLATED")
        original_context = self._context(request0)
        with self.assertRaisesRegex(AdapterContractViolation, "EVALUATOR_OUTPUT_REPLAY_REQUEST_MISMATCH"):
            bind_evaluator_output(request1, captured_output, original_context)

    def test_response_challenge_digest_mismatch_is_rejected(self) -> None:
        response = self._response()
        response["challenge_digest"] = "f" * 64
        with self.assertRaisesRegex(AdapterContractViolation, "RESPONSE_CHALLENGE_DIGEST_MISMATCH"):
            validate_response(self.requests[0], response)

    def test_response_profile_digest_mismatch_is_rejected(self) -> None:
        response = self._response()
        response["protected_relation_profile_digest"] = "f" * 64
        with self.assertRaisesRegex(AdapterContractViolation, "RESPONSE_PROTECTED_RELATION_DIGEST_MISMATCH"):
            validate_response(self.requests[0], response)

    def test_adapter_failure_is_scored_separately(self) -> None:
        request = self.requests[0]
        transcript = self._run_python(request, "raise RuntimeError('boom')")
        report = score_results([request], [transcript])
        self.assertEqual(report["semantic_responses"], 0)
        self.assertEqual(sum(report["classifications"].values()), 0)
        self.assertEqual(report["adapter_failures"], {"PROCESS_ERROR": 1})
        self.assertEqual(report["adapter_failure_total"], 1)

    def test_complete_mismatch_taxonomy(self) -> None:
        expected = {
            ("VIOLATED", "PRESERVED"): "UNSAFE_FALSE_PRESERVATION",
            ("UNVERIFIABLE", "PRESERVED"): "UNSAFE_UNVERIFIABLE_UPGRADE",
            ("PRESERVED", "VIOLATED"): "FALSE_VIOLATION",
            ("PRESERVED", "UNVERIFIABLE"): "PRESERVATION_NOT_ESTABLISHED",
            ("VIOLATED", "UNVERIFIABLE"): "VIOLATION_NOT_ESTABLISHED",
            ("UNVERIFIABLE", "VIOLATED"): "UNVERIFIABLE_MISCLASSIFIED_AS_VIOLATION",
        }
        self.assertEqual({pair: classify(*pair) for pair in expected}, expected)

    def test_transcript_binds_request_output_invocation_and_response(self) -> None:
        transcript = self._reference_transcripts()[0]
        self.assertEqual(transcript["request_digest"], digest_value(self.requests[0]))
        self.assertEqual(transcript["response_digest"], digest_value(transcript["normalized_response"]))
        self.assertEqual(transcript["evaluator_output_digest"], digest_value(transcript["evaluator_output"]))
        self.assertEqual(transcript["invocation_digest"], digest_value(transcript["invocation"]))
        self.assertEqual(transcript["invocation"]["request_digest"], digest_value(self.requests[0]))
        raw = transcript["raw_response"].encode("utf-8")
        self.assertEqual(transcript["raw_response_digest"], hashlib.sha256(raw).hexdigest())
        stderr = transcript["stderr"].encode("utf-8")
        self.assertEqual(transcript["stderr_digest"], hashlib.sha256(stderr).hexdigest())
        self.assertFalse(transcript["timestamp_authoritative"])

    def test_every_frozen_inventory_path_matches_immutable_v0_tag(self) -> None:
        tag_commit = subprocess.run(
            ["git", "rev-parse", "v0^{commit}"], cwd=ROOT, check=True, capture_output=True, text=True
        ).stdout.strip()
        tag_tree = subprocess.run(
            ["git", "rev-parse", "v0^{tree}"], cwd=ROOT, check=True, capture_output=True, text=True
        ).stdout.strip()
        self.assertEqual(tag_commit, V0_COMMIT)
        self.assertEqual(tag_tree, V0_TREE)
        inventory_path = ROOT / "releases/v0/sha256-inventory.json"
        self.assertEqual(hashlib.sha256(inventory_path.read_bytes()).hexdigest(), V0_INVENTORY_SHA256)
        inventory = json.loads(inventory_path.read_text(encoding="utf-8"))
        for entry in inventory["entries"]:
            with self.subTest(path=entry["path"]):
                tag_bytes = subprocess.run(
                    ["git", "show", f"v0:{entry['path']}"], cwd=ROOT, check=True, capture_output=True
                ).stdout
                current = (ROOT / entry["path"]).read_bytes()
                self.assertEqual(current, tag_bytes)
                self.assertEqual(len(current), entry["byte_length"])
                self.assertEqual(hashlib.sha256(current).hexdigest(), entry["sha256"])


if __name__ == "__main__":
    unittest.main()
