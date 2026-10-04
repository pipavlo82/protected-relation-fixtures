"""Two identified domain adapters. No claim of independent implementation."""
from __future__ import annotations

from copy import deepcopy

try:
    from tools.award_actual_settlement import relation
    from tools.guarantee_preservation import VERSION, PROFILE, ContractError, digest, load_json, require
except ModuleNotFoundError:
    from award_actual_settlement import relation
    from guarantee_preservation import VERSION, PROFILE, ContractError, digest, load_json, require

PRF_PIN = "fac26d2e8346aeab08194343b78c345d235c6935"
KIT_PIN = "a725f2e6aa0d887b8bd51d9081c07dbcad5c9c87"
COMMON_NONCLAIMS = ["dependency_basis_completeness_or_soundness",
                    "independent_implementation_interoperability", "accepted_standard"]


def _context(payload, guarantee, scope, assumptions, authority, version):
    return {"guarantee_id": guarantee, "subject": digest(payload), "scope": scope,
            "assumptions": assumptions, "authority": authority, "version": version}


def _native(output, verdict_field, grade_field=None):
    return {"output": deepcopy(output),
            "verdict": {"field": verdict_field, "value": output[verdict_field]},
            "reason": {"present": "reason" in output, "value": output.get("reason")},
            "evidence_grade": {"present": grade_field in output if grade_field else False,
                               "value": output.get(grade_field) if grade_field else None}}


def _check(name, evaluator, outcome, establishes, nonclaims):
    return {"dependency_id": name, "evaluator_ref": evaluator, "outcome": outcome,
            "evidence_refs": ["native-input", "native-output"],
            "establishes": [establishes] if outcome == "TRUE" else [],
            "does_not_establish": nonclaims}


def _evidence(payload, native_output):
    return [{"ref": "native-input", "kind": "supplied-input", "payload": deepcopy(payload),
             "digest": digest(payload)},
            {"ref": "native-output", "kind": "native-output", "payload": deepcopy(native_output),
             "digest": digest(native_output)}]


def _read_evidence(envelope):
    evidence = envelope["evidence"]
    require(len(evidence) == 2 and {e["ref"] for e in evidence} == {"native-input", "native-output"},
            "missing_or_ambiguous_native_evidence")
    by_ref = {item["ref"]: item for item in evidence}
    for item in evidence:
        require(item["digest"] == digest(item["payload"]), "evidence_digest_mismatch")
    require(by_ref["native-input"]["kind"] == "supplied-input"
            and by_ref["native-output"]["kind"] == "native-output", "evidence_kind_mismatch")
    return by_ref["native-input"]["payload"], by_ref["native-output"]["payload"]


def _envelope(adapter, payload, native_output, evidence_class, basis):
    evaluation = adapter.evaluate(payload, native_output)
    dependencies = list(adapter.dependencies)
    return {"schema_version": VERSION, "adapter_ref": adapter.adapter_ref,
            "evaluator_ref": adapter.evaluator_ref, "context": evaluation["context"],
            "depends_on": dependencies, "depends_on_digest": digest(dependencies),
            "dependency_basis": {"id": basis["id"], "digest": digest(basis)},
            "evidence_class": evidence_class, "evidence": _evidence(payload, native_output),
            "native": evaluation["native"], "checks": list(evaluation["checks"].values()),
            "does_not_establish": evaluation["does_not_establish"]}


class AwardSettlementAdapter:
    adapter_ref = "prf-award-actual-settlement-adapter-v0"
    evaluator_ref = "prf-supplied-tuple-evaluator-v0"
    dependencies = ("supplied_input_binding", "award_settlement_relation")
    evidence_classes = ("SYNTHETIC_CONDITIONAL_MODEL",)
    nonclaims = COMMON_NONCLAIMS + ["universal_mechanism_truthfulness", "chain_execution",
                                  "award_authority_or_provenance", "version_authenticity"]
    def evaluate(self, payload, native_output):
        require(isinstance(payload, dict) and set(payload) == {"award", "settlements"},
                "unsupported_prf_input")
        actual = relation(payload["award"], payload["settlements"])
        require(native_output == actual, "prf_native_result_not_recomputed")
        context = _context({"input": payload, "native_output": native_output}, "supplied-award-actual-settlement-tuple-preserved",
                           "one supplied synthetic award and observed settlement list",
                           ["same accepted successful performance at true cost", "loser incurs no work cost",
                            "reveal bond refunded", "equal normalized transaction costs",
                            "no authenticated chain or award-authority evidence"],
                           {"id": "caller-supplied-synthetic-tuples",
                            "semantics": "tuple comparison only; opaque refs confer no authority"},
                           "award-actual-settlement-v0@" + PRF_PIN)
        outcome = {"PRESERVED": "TRUE", "VIOLATED": "FALSE", "UNVERIFIABLE": "UNKNOWN"}[actual["outcome"]]
        checks = {
            "supplied_input_binding": _check("supplied_input_binding", self.evaluator_ref, "TRUE",
                                            "exact supplied input identity", self.nonclaims),
            "award_settlement_relation": _check("award_settlement_relation", self.evaluator_ref, outcome,
                                                context["guarantee_id"], self.nonclaims)}
        return {"context": context, "native": _native(actual, "outcome"),
                "checks": checks, "does_not_establish": self.nonclaims,
                "applicable": True, "admissible": True}
    def adapt(self, payload, *, basis, native_output=None, evidence_class="SYNTHETIC_CONDITIONAL_MODEL"):
        native_output = relation(payload.get("award"), payload.get("settlements")) if native_output is None else native_output
        return _envelope(self, payload, native_output, evidence_class, basis)
    def verify(self, envelope):
        payload, output = _read_evidence(envelope)
        return self.evaluate(payload, output)


class ScanGradeAdapter:
    adapter_ref = "kit59-authentication-grade-adapter-v0"
    evaluator_ref = "kit59-pinned-contract-evaluator-v0"
    dependencies = ("supplied_input_binding", "authentication_grade_transfer")
    evidence_classes = ("PINNED_SOURCE_EXPECTATION", "EXTERNAL_NATIVE_OUTPUT_COMPARISON", "SYNTHETIC_NATIVE_MUTATION")
    nonclaims = COMMON_NONCLAIMS + ["underlying_scan_assertion_truth", "poisoning_absence",
                                  "scanner_origin_execution", "operational_authorization",
                                  "freshness_or_revocation", "upstream_checker_execution"]
    def evaluate(self, payload, native_output):
        fixtures = load_json(PROFILE / "kit59-fixtures.json")
        # Exact input identities come from reviewed pinned fixtures, not case names
        # supplied by a producer and not an untrusted native output's bindings.
        known = [item for item in fixtures["fixtures"] if digest(item["input"]) == digest(payload)]
        require(len(known) == 1, "unrecognized_pinned_kit_input")
        source = known[0]
        expected = source["source_derived_native"]["result"]
        controls = [source["source_derived_native"], *source["native_controls"].values()]
        require(digest(native_output) in {digest(item) for item in controls},
                "unsupported_native_observation_or_mutation")
        require(isinstance(native_output, dict) and set(native_output) == {"case_id", "reproduced", "result"}
                and native_output["case_id"] == payload["case_id"]
                and type(native_output["reproduced"]) is bool, "unsupported_kit_native_row")
        result = native_output["result"]
        fields = set(expected)
        require(isinstance(result, dict) and set(result) == fields, "unsupported_kit_native_shape")
        require(result["replay_bindings"] in ("valid", "FAIL")
                and result["result_only_check"] in ("VALID", "NOT_VALID")
                and result["subject_bound_check"] in ("NO_FINDING", "CANNOT_ESTABLISH", "CONTRADICTED", "NOT_VALID")
                and result["evidence_grade"] in ("AUTHENTICATED_REPORT", "REPRODUCED", None),
                "unknown_kit_native_value")
        if "replay_failures" in fields:
            require(isinstance(result["replay_failures"], list)
                    and all(isinstance(v, str) for v in result["replay_failures"]),
                    "unsupported_replay_failures")
        require(result["result_only_check"] == expected["result_only_check"],
                "unrelated_native_result_mismatch")
        context = _context({"input": payload, "native_output": native_output}, "pinned-scan-authentication-to-grade-transfer-preserved",
                           "one pinned k=1 scan fixture; report/replay grading gates only",
                           ["reviewed pinned fixture/source expectation contract",
                            "fixed public test key; no origin or operational authority",
                            "k=1; recordwise corpus-to-subset requires all inclusion proofs",
                            "native reproduced flag is expectation conformance only"],
                           {"id": "recompute-kit-public-test-key@" + KIT_PIN,
                            "semantics": "source-expectation model; no live key authority/freshness"},
                           "scan_subject_binding.v0@" + KIT_PIN)
        # Authentication FALSE is an independently pinned predicate here, not
        # evidence that the underlying scan assertion itself is false.
        grade_pair = (result["subject_bound_check"], result["evidence_grade"])
        expected_pair = (expected["subject_bound_check"], expected["evidence_grade"])
        promoted = result["evidence_grade"] is not None or result["subject_bound_check"] in ("NO_FINDING", "CONTRADICTED")
        replay_promoted = expected["replay_bindings"] == "FAIL" and (
            result["replay_bindings"] == "valid" or result.get("replay_failures") != expected.get("replay_failures"))
        if replay_promoted or (grade_pair != expected_pair and promoted):
            outcome = "FALSE"
        elif result != expected:
            outcome = "UNKNOWN"
        elif expected["evidence_grade"] is None:
            outcome = "UNKNOWN"
        else:
            outcome = "TRUE"
        native = _native(result, "subject_bound_check", "evidence_grade")
        # Preserve the complete native row, including expectation-conformance.
        native["output"] = deepcopy(native_output)
        native["signature_predicate"] = source["signature_predicate"]
        native["scan_assertion"] = "UNKNOWN" if expected["evidence_grade"] is None else "NATIVE_SCOPED"
        checks = {
            "supplied_input_binding": _check("supplied_input_binding", self.evaluator_ref, "TRUE",
                                            "exact pinned fixture input identity", self.nonclaims),
            "authentication_grade_transfer": _check("authentication_grade_transfer", self.evaluator_ref, outcome,
                                                     context["guarantee_id"], self.nonclaims)}
        return {"context": context, "native": native, "checks": checks,
                "does_not_establish": self.nonclaims, "applicable": True, "admissible": True}
    def adapt(self, payload, *, basis, native_output, evidence_class="PINNED_SOURCE_EXPECTATION"):
        return _envelope(self, payload, native_output, evidence_class, basis)
    def verify(self, envelope):
        payload, output = _read_evidence(envelope)
        return self.evaluate(payload, output)


def registry():
    adapters = (AwardSettlementAdapter(), ScanGradeAdapter())
    return {adapter.adapter_ref: adapter for adapter in adapters}
