from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch

from tools.guarantee_preservation import (PROFILE, VERSION, SCHEMA_PATH, consume, digest,
                                         load_json, validate_schema, ContractError)
from tools.guarantee_preservation_adapters import registry, ScanGradeAdapter
from tools.validate_guarantee_preservation import prepare, run_suite, compare_external

ROOT = Path(__file__).resolve().parents[1]


class GuaranteePreservationTests(unittest.TestCase):
    def setUp(self):
        self.envelope, self.policy, self.basis, _ = prepare("prf-price_preserving")

    def decision(self, envelope=None, policy=None, basis=None, adapters=None):
        return consume(self.envelope if envelope is None else envelope,
                       policy=self.policy if policy is None else policy,
                       accepted_basis=self.basis if basis is None else basis,
                       registry=registry() if adapters is None else adapters)

    def withheld(self, decision, outcome="UNVERIFIABLE"):
        self.assertEqual(decision["outcome"], outcome)
        self.assertIsNone(decision["guarantee"])
        self.assertEqual(decision["establishes"], [])

    def reseal_basis(self):
        self.policy["accepted_basis_digest"] = digest(self.basis)
        self.envelope["dependency_basis"] = {"id": self.basis["id"], "digest": digest(self.basis)}

    def test_both_domains_schema_first_and_exact_native_preservation(self):
        report = run_suite()
        self.assertEqual(report["counts"], {"PRESERVED": 4, "VIOLATED": 5, "UNVERIFIABLE": 2})
        self.assertEqual(len(report["results"]), 11)

    def test_prf_payment_violation_retains_native_reason(self):
        envelope, policy, basis, _ = prepare("prf-fixed_reward_substitution")
        result = self.decision(envelope, policy, basis)
        self.withheld(result, "VIOLATED")
        self.assertEqual(result["native"], envelope["native"])
        self.assertEqual(result["native"]["reason"], {"present": True, "value": "amount_mismatch"})
        self.assertEqual(result["native"]["evidence_grade"], {"present": False, "value": None})

    def test_missing_prf_payment_is_not_refutation(self):
        envelope, policy, basis, _ = prepare("prf-missing_payment")
        self.withheld(self.decision(envelope, policy, basis))

    def test_invalid_signature_native_abstention_and_reason_absence(self):
        envelope, policy, basis, _ = prepare("kit-c6")
        result = self.decision(envelope, policy, basis)
        self.withheld(result)
        native = result["native"]
        self.assertEqual(native["verdict"]["value"], "CANNOT_ESTABLISH")
        self.assertEqual(native["evidence_grade"], {"present": True, "value": None})
        self.assertEqual(native["reason"], {"present": False, "value": None})
        self.assertEqual(native["signature_predicate"], "FALSE")
        self.assertEqual(native["scan_assertion"], "UNKNOWN")
        self.assertTrue(native["output"]["reproduced"])

    def test_native_contradicted_is_not_bent_to_mapped_violation(self):
        envelope, policy, basis, _ = prepare("kit-c4b")
        result = self.decision(envelope, policy, basis)
        self.assertEqual(result["outcome"], "PRESERVED")
        self.assertEqual(result["native"]["verdict"]["value"], "CONTRADICTED")
        self.assertEqual(result["native"]["evidence_grade"]["value"], "REPRODUCED")
        self.assertIn("underlying_scan_assertion_truth", result["does_not_establish"])

    def test_m8_and_m9_refute_only_selected_gate_relation(self):
        for name in ("M8-replay-signature-guard-removed", "M9-grade-signature-guard-removed"):
            with self.subTest(name=name):
                envelope, policy, basis, _ = prepare("kit-" + name)
                result = self.decision(envelope, policy, basis)
                self.withheld(result, "VIOLATED")
                self.assertEqual(result["native"]["scan_assertion"], "UNKNOWN")
                self.assertEqual(result["native"]["signature_predicate"], "FALSE")
                self.assertEqual(result["native"], envelope["native"])

    def test_wrong_subject_version_scope_authority_and_assumptions(self):
        changes = {"subject": "sha256:" + "0" * 64, "version": "future-version",
                   "scope": "all mechanisms", "authority": {"id": "chain", "semantics": "verified"},
                   "assumptions": ["missing economic costs"], "guarantee_id": "universal-truthfulness"}
        for key, value in changes.items():
            with self.subTest(key=key):
                altered = deepcopy(self.envelope)
                altered["context"][key] = value
                self.withheld(self.decision(altered))

    def test_even_selected_policy_cannot_promote_native_domain_scope(self):
        for key, value in (("guarantee_id", "universal-mechanism-truthfulness"),
                           ("authority", {"id": "verified-chain-authority", "semantics": "actual provenance"}),
                           ("version", "authenticated-task-version")):
            envelope, policy, basis, _ = prepare("prf-price_preserving")
            for context in (envelope["context"], policy["context"], basis["context"]):
                context[key] = value
            policy["accepted_basis_digest"] = digest(basis)
            envelope["dependency_basis"]["digest"] = digest(basis)
            self.withheld(self.decision(envelope, policy, basis))

    def test_missing_evidence_both_domains(self):
        for name in ("prf-price_preserving", "kit-c2"):
            envelope, policy, basis, _ = prepare(name)
            envelope["evidence"].pop()
            self.withheld(self.decision(envelope, policy, basis))

    def test_evidence_digest_mismatch(self):
        self.envelope["evidence"][0]["digest"] = "sha256:" + "0" * 64
        self.withheld(self.decision())

    def test_output_substitution_without_policy_rebinding(self):
        envelope, policy, basis, _ = prepare("kit-c6")
        fixture = next(f for f in load_json(PROFILE / "kit59-fixtures.json")["fixtures"] if f["id"] == "c6")
        mutated = registry()[envelope["adapter_ref"]].adapt(
            fixture["input"], basis=basis,
            native_output=fixture["native_controls"]["M9-grade-signature-guard-removed"],
            evidence_class="SYNTHETIC_NATIVE_MUTATION")
        self.withheld(self.decision(mutated, policy, basis))

    def test_malformed_or_unsupported_kit_native_is_unverifiable(self):
        envelope, policy, basis, _ = prepare("kit-c2")
        for field, value in (("evidence_grade", "UNIVERSALLY_SAFE"),
                             ("subject_bound_check", "POISONING_ABSENT")):
            altered = deepcopy(envelope)
            evidence = next(e for e in altered["evidence"] if e["ref"] == "native-output")
            evidence["payload"]["result"][field] = value
            evidence["digest"] = digest(evidence["payload"])
            self.withheld(self.decision(altered, policy, basis))

    def test_unknown_adapter_and_evaluator(self):
        for field in ("adapter_ref", "evaluator_ref"):
            altered = deepcopy(self.envelope)
            altered[field] = "unknown"
            self.withheld(self.decision(altered))

    def test_registry_required_and_consumer_authorization(self):
        self.withheld(self.decision(adapters={}))
        self.policy["allowed_adapters"] = []
        self.withheld(self.decision())

    def test_malformed_consumer_trust_inputs_fail_closed(self):
        for field in ("allowed_adapters", "allowed_evidence_classes"):
            altered = deepcopy(self.policy)
            altered[field] = "prefix-" + altered[field][0] + "-suffix"
            self.withheld(self.decision(policy=altered))
        for identity in (None, "", 7):
            altered = deepcopy(self.policy)
            altered["id"] = identity
            self.withheld(self.decision(policy=altered))
        for invalid_registry in (None, [], "registry"):
            result = consume(self.envelope, policy=self.policy, accepted_basis=self.basis,
                             registry=invalid_registry)
            self.withheld(result)
        for acceptance in (None, [], "accepted"):
            altered = deepcopy(self.basis)
            altered["acceptance"] = acceptance
            policy = deepcopy(self.policy)
            policy["accepted_basis_digest"] = digest(altered)
            envelope = deepcopy(self.envelope)
            envelope["dependency_basis"]["digest"] = digest(altered)
            self.withheld(self.decision(envelope, policy, altered))

    def test_unknown_mandatory_dependency_and_missing_check(self):
        altered = deepcopy(self.envelope)
        altered["checks"][0]["dependency_id"] = "unknown"
        self.withheld(self.decision(altered))
        self.envelope["checks"].pop()
        self.withheld(self.decision())

    def test_omitted_dependency_cannot_hide_refutation(self):
        envelope, policy, basis, _ = prepare("prf-fixed_reward_substitution")
        envelope["depends_on"] = ["supplied_input_binding"]
        envelope["depends_on_digest"] = digest(envelope["depends_on"])
        envelope["checks"] = envelope["checks"][:1]
        self.withheld(self.decision(envelope, policy, basis))

    def test_empty_list_never_vacuously_preserved(self):
        self.envelope["depends_on"] = []
        self.envelope["depends_on_digest"] = digest([])
        self.envelope["checks"] = []
        self.withheld(self.decision())

    def test_dependency_digest_mismatch(self):
        self.envelope["depends_on_digest"] = "sha256:" + "0" * 64
        self.withheld(self.decision())

    def test_dependency_basis_digest_is_not_acceptance(self):
        self.basis["acceptance"]["status"] = "PRODUCER_APPROVED"
        self.reseal_basis()
        self.withheld(self.decision())

    def test_missing_acceptance_basis_and_empty_basis(self):
        for kind in ("missing", "empty"):
            self.setUp()
            if kind == "missing":
                self.basis.pop("acceptance")
            else:
                self.basis["mandatory"] = {}
            self.reseal_basis()
            self.withheld(self.decision())

    def test_producer_self_approval_flag_cannot_select_policy(self):
        self.envelope["accepted"] = True
        self.envelope["policy_id"] = self.policy["id"]
        self.withheld(self.decision())

    def test_unsupported_and_circular_basis(self):
        for kind in ("rule", "edge", "cycle", "evaluator", "omission"):
            self.setUp()
            if kind == "rule":
                self.basis["rule"] = "producer-proves-completeness"
            elif kind == "edge":
                self.basis["mandatory"]["supplied_input_binding"]["requires"] = ["future_consumer_result"]
            elif kind == "cycle":
                self.basis["mandatory"]["supplied_input_binding"]["requires"] = ["award_settlement_relation"]
            elif kind == "evaluator":
                self.basis["mandatory"]["award_settlement_relation"]["evaluator_ref"] = "unknown"
            else:
                self.basis["mandatory"].pop("award_settlement_relation")
            self.reseal_basis()
            self.withheld(self.decision())

    def test_conflicting_evidence_withholds_without_majority_vote(self):
        false = deepcopy(self.envelope["checks"][0])
        false["outcome"] = "FALSE"
        self.envelope["checks"].extend([deepcopy(self.envelope["checks"][0]), false])
        result = self.decision()
        self.withheld(result)
        self.assertEqual(result["reason"], "conflicting_evidence")

    def test_legitimate_redundancy_is_preserved_not_native_cardinality(self):
        self.envelope["checks"].append(deepcopy(self.envelope["checks"][0]))
        self.assertEqual(self.decision()["outcome"], "PRESERVED")
        envelope, policy, basis, _ = prepare("prf-repeated_settlement")
        self.withheld(self.decision(envelope, policy, basis), "VIOLATED")

    def test_claimed_predicate_cannot_replace_adapter_evidence(self):
        envelope, policy, basis, _ = prepare("prf-fixed_reward_substitution")
        envelope["checks"][1]["outcome"] = "TRUE"
        self.withheld(self.decision(envelope, policy, basis))

    def test_native_metadata_cannot_be_rewritten(self):
        for name in ("prf-price_preserving", "kit-c2", "kit-c6"):
            for field, key, value in (("reason", "value", "universal guarantee"),
                                      ("reason", "present", True),
                                      ("verdict", "value", "PRESERVED"),
                                      ("evidence_grade", "value", "REPRODUCED"),
                                      ("evidence_grade", "present", False)):
                envelope, policy, basis, _ = prepare(name)
                if envelope["native"][field][key] == value:
                    continue
                with self.subTest(name=name, field=field, key=key):
                    envelope["native"][field][key] = value
                    self.withheld(self.decision(envelope, policy, basis))

    def test_evidence_class_is_consumer_admitted(self):
        self.envelope["evidence_class"] = "VERIFIED_CHAIN"
        self.withheld(self.decision())

    def test_consumer_policy_cannot_admit_unsupported_adapter_class(self):
        self.envelope["evidence_class"] = "UNSUPPORTED_PROVENANCE"
        self.policy["allowed_evidence_classes"].append("UNSUPPORTED_PROVENANCE")
        self.withheld(self.decision())

    def test_exported_decision_retains_exact_subject_and_basis_bindings(self):
        result = self.decision()
        self.assertEqual(result["context"], self.policy["context"])
        self.assertEqual(result["observation_bindings"]["context"], self.envelope["context"])
        self.assertEqual(result["observation_bindings"]["dependency_basis"], self.envelope["dependency_basis"])
        self.assertEqual(result["envelope_digest"], digest(self.envelope))
        self.assertEqual(result["policy_digest"], digest(self.policy))
        self.assertEqual(len(result["evidence_digests"]), 2)

    def test_does_not_establish_cannot_be_dropped(self):
        self.envelope["does_not_establish"] = ["accepted_standard"]
        self.withheld(self.decision())

    def test_applicability_and_admissibility_precede_false_aggregation(self):
        envelope, policy, basis, _ = prepare("prf-fixed_reward_substitution")
        adapter = registry()[envelope["adapter_ref"]]
        original = adapter.verify
        for field in ("applicable", "admissible"):
            def altered(candidate, field=field):
                result = original(candidate)
                result[field] = False
                return result
            with patch.object(adapter, "verify", altered):
                self.withheld(self.decision(envelope, policy, basis, {adapter.adapter_ref: adapter}))

    def test_unknown_dependency_with_false_relation_is_unverifiable(self):
        envelope, policy, basis, _ = prepare("prf-fixed_reward_substitution")
        adapter = registry()[envelope["adapter_ref"]]
        original = adapter.verify
        envelope["checks"][0]["outcome"] = "UNKNOWN"
        envelope["checks"][0]["establishes"] = []
        def altered(candidate):
            result = original(candidate)
            result["checks"]["supplied_input_binding"] = deepcopy(envelope["checks"][0])
            return result
        with patch.object(adapter, "verify", altered):
            self.withheld(self.decision(envelope, policy, basis, {adapter.adapter_ref: adapter}))

    def test_duplicate_json_keys_and_nonfinite_numbers_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            p = Path(temporary) / "bad.json"
            for data in ('{"x":1,"x":2}', '{"x":NaN}'):
                p.write_text(data, encoding="utf-8")
                with self.assertRaises(ContractError):
                    load_json(p)

    def test_external_handoff_preserves_raw_capture_without_execution_claim(self):
        fixtures = load_json(PROFILE / "kit59-fixtures.json")["fixtures"]
        capture = {"profile": "scan_subject_binding.v0",
                   "results": [f["source_derived_native"] for f in fixtures], "total": 4, "reproduced": 4}
        raw = (json.dumps(capture, indent=4) + "\n").encode()
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "synthetic-contract-output.json"
            vectors = Path(temporary) / "vectors.json"
            output.write_bytes(raw)
            first = fixtures[0]["input"]
            # Offline contract exercise only; raw upstream hash is independently
            # verified during import, patched here to avoid network/native execution.
            vectors.write_text(json.dumps({"cases": {f["input"]["case_id"]: f["input"]["case"] for f in fixtures},
                                           "test_public_key_ed25519": first["test_public_key_ed25519"],
                                           "toy_scan": first["toy_scan"]}), encoding="utf-8")
            actual_hashlib = hashlib.sha256
            vector_snapshot = vectors.read_bytes()
            actual_read = Path.read_bytes
            reads = {vectors: 0, output: 0}
            def snapshot_read(path):
                if path in reads:
                    reads[path] += 1
                return actual_read(path)
            class VectorDigest:
                def hexdigest(self):
                    return first["vectors_sha256"]
            def hash_control(data=b""):
                return VectorDigest() if data == vector_snapshot else actual_hashlib(data)
            with patch("tools.validate_guarantee_preservation.hashlib.sha256", hash_control), patch.object(Path, "read_bytes", snapshot_read):
                report = compare_external(vectors, output, "policy-kit-c2")
            self.assertEqual(reads, {vectors: 1, output: 1})
            self.assertEqual(report["native_capture"], capture)
            self.assertEqual(report["native_file_sha256"], actual_hashlib(raw).hexdigest())
            self.assertEqual(report["decision"]["outcome"], "PRESERVED")
            self.assertEqual(output.read_bytes(), raw)
            self.assertIn("not established", report["execution_provenance"])

    def test_validator_cli_deterministic_normal_repeat_optimized(self):
        commands = ([sys.executable, "-B", str(ROOT / "tools/validate_guarantee_preservation.py")],
                    [sys.executable, "-B", str(ROOT / "tools/validate_guarantee_preservation.py")],
                    [sys.executable, "-B", "-O", str(ROOT / "tools/validate_guarantee_preservation.py")])
        outputs = [subprocess.run(command, cwd=ROOT, capture_output=True, check=True).stdout for command in commands]
        self.assertEqual(outputs[0], outputs[1])
        self.assertEqual(outputs[0], outputs[2])

    def test_profile_bytes_are_lf_and_schema_valid(self):
        for path in PROFILE.iterdir():
            if path.is_file():
                raw = path.read_bytes()
                self.assertFalse(raw.startswith(b"\xef\xbb\xbf"), path)
                self.assertNotIn(b"\r", raw, path)
                self.assertTrue(raw.endswith(b"\n") and not raw.endswith(b"\n\n"), path)
        validate_schema(self.envelope)


if __name__ == "__main__":
    unittest.main()
