"""Offline schema-first exercises and explicit external #59 output comparison."""
from __future__ import annotations

import argparse
import hashlib
import json
from copy import deepcopy
from pathlib import Path

try:
    from tools.award_actual_settlement import load_suite as load_prf_suite, relation
    from tools.guarantee_preservation import (PROFILE, VERSION, SCHEMA_PATH, ContractError,
                                             consume, load_json, parse_json, require, select_inputs, validate_schema)
    from tools.guarantee_preservation_adapters import KIT_PIN, registry
except ModuleNotFoundError:
    from award_actual_settlement import load_suite as load_prf_suite, relation
    from guarantee_preservation import (PROFILE, VERSION, SCHEMA_PATH, ContractError,
                                       consume, load_json, parse_json, require, select_inputs, validate_schema)
    from guarantee_preservation_adapters import KIT_PIN, registry


def configuration():
    return load_json(PROFILE / "consumer-inputs.json")


def prepare(case_id):
    suite = load_json(PROFILE / "suite.json")
    selected = [case for case in suite["cases"] if case["id"] == case_id]
    require(len(selected) == 1, "unknown_exercise")
    case = selected[0]
    config = configuration()
    policy = config["policies"][case["policy_id"]]
    basis = config["accepted_bases"][policy["basis_id"]]
    adapter = registry()[case["adapter_ref"]]
    domain, ref = case["input_ref"].split(":", 1)
    if domain == "prf":
        native_case = next(item for item in load_prf_suite()["cases"] if item["id"] == ref)
        payload = {"award": native_case.get("award"), "settlements": native_case.get("settlements")}
        native_output = relation(**payload)
    elif domain == "kit":
        fixture = next(item for item in load_json(PROFILE / "kit59-fixtures.json")["fixtures"] if item["id"] == ref)
        payload = fixture["input"]
        native_output = (fixture["source_derived_native"] if case["native_ref"] == "baseline"
                         else fixture["native_controls"][case["native_ref"]])
    else:
        raise ContractError("unknown_exercise_domain")
    envelope = adapter.adapt(payload, basis=basis, native_output=native_output,
                             evidence_class=case["evidence_class"])
    return deepcopy(envelope), deepcopy(policy), deepcopy(basis), case["expected_outcome"]


def validate_source_lock():
    lock = load_json(PROFILE / "source-lock.json")
    require(lock.get("schema_version") == VERSION and isinstance(lock.get("files"), dict)
            and bool(lock["files"]), "unsupported_source_lock")
    root = PROFILE.parents[1]
    for relative, expected in lock["files"].items():
        path = (root / relative).resolve()
        require(path.is_relative_to(root.resolve()) and path.is_file(), "unavailable_locked_source")
        require(hashlib.sha256(path.read_bytes()).hexdigest() == expected,
                "locked_source_digest_mismatch:" + relative)
    return hashlib.sha256((PROFILE / "source-lock.json").read_bytes()).hexdigest()


def run_suite(consumer=consume, adapters=None):
    source_lock_sha256 = validate_source_lock()
    adapters = registry() if adapters is None else adapters
    cases = load_json(PROFILE / "suite.json")["cases"]
    require(len(cases) == 11 and len({case["id"] for case in cases}) == 11, "exercise_coverage_changed")
    results = []
    for case in cases:
        envelope, policy, basis, expected = prepare(case["id"])
        validate_schema(envelope)
        decision = consumer(envelope, policy=policy, accepted_basis=basis, registry=adapters)
        require(decision["outcome"] == expected, "exercise_mismatch:" + case["id"])
        require(decision["native"] == envelope["native"], "native_result_not_preserved:" + case["id"])
        require((decision["guarantee"] is not None) == (expected == "PRESERVED"),
                "guarantee_not_withheld:" + case["id"])
        results.append({"id": case["id"], "decision": decision})
    return {"schema_version": VERSION,
            "schema_sha256": hashlib.sha256(SCHEMA_PATH.read_bytes()).hexdigest(),
            "source_lock_sha256": source_lock_sha256,
            "provenance": "own PRF execution; kit pinned source-derived contract exercises, no upstream execution",
            "results": results,
            "counts": {outcome: sum(item["decision"]["outcome"] == outcome for item in results)
                       for outcome in ("PRESERVED", "VIOLATED", "UNVERIFIABLE")}}


def compare_external(vectors_path, output_path, policy_id):
    config = configuration()
    require(policy_id in config["policies"], "unknown_consumer_policy")
    policy = config["policies"][policy_id]
    basis = config["accepted_bases"][policy["basis_id"]]
    vector_raw = Path(vectors_path).read_bytes()
    output_raw = Path(output_path).read_bytes()
    vector_hash = hashlib.sha256(vector_raw).hexdigest()
    require(vector_hash == "f9a1b3e547a55caf498f14ced1e239171f843fb9c81aa6e279fd6fd3f7446e89",
            "external_vectors_pin_mismatch")
    vectors = parse_json(vector_raw)
    capture = parse_json(output_raw)
    require(isinstance(capture, dict) and capture.get("profile") == "scan_subject_binding.v0"
            and isinstance(capture.get("results"), list), "unsupported_external_native_capture")
    fixtures = load_json(PROFILE / "kit59-fixtures.json")["fixtures"]
    matching = []
    for fixture in fixtures:
        name = fixture["input"]["case_id"]
        rows = [row for row in capture["results"] if isinstance(row, dict) and row.get("case_id") == name]
        require(len(rows) <= 1, "duplicate_external_native_row")
        if not rows:
            continue
        payload = {"case_id": name, "case": vectors["cases"][name],
                   "test_public_key_ed25519": vectors["test_public_key_ed25519"], "toy_scan": vectors["toy_scan"],
                   "source_pin": KIT_PIN, "vectors_sha256": vector_hash}
        adapter = registry()["kit59-authentication-grade-adapter-v0"]
        evaluation = adapter.evaluate(payload, rows[0])
        if evaluation["context"] != policy["context"]:
            continue
        envelope = adapter.adapt(payload, native_output=rows[0], basis=basis,
                                 evidence_class="EXTERNAL_NATIVE_OUTPUT_COMPARISON")
        selected_policy = deepcopy(policy)
        # Caller explicitly chooses this comparison mode; the local fixture policy
        # authorizes it without asserting that these bytes prove their execution.
        require("EXTERNAL_NATIVE_OUTPUT_COMPARISON" in selected_policy["allowed_evidence_classes"],
                "external_comparison_not_authorized")
        matching.append(consume(envelope, policy=selected_policy, accepted_basis=basis, registry=registry()))
    require(len(matching) == 1, "no_unique_external_observation_for_selected_policy")
    return {"schema_version": VERSION,
            "schema_sha256": hashlib.sha256(SCHEMA_PATH.read_bytes()).hexdigest(),
            "vectors_file_sha256": vector_hash,
            "native_file_sha256": hashlib.sha256(output_raw).hexdigest(),
            "native_capture": capture, "decision": matching[0],
            "execution_provenance": "caller-supplied bytes; execution/origin not established by this comparison"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--envelope", type=Path)
    parser.add_argument("--policy-id")
    parser.add_argument("--kit-vectors", type=Path)
    parser.add_argument("--kit-native-output", type=Path)
    args = parser.parse_args()
    try:
        validate_source_lock()
        if args.envelope:
            require(args.policy_id and not args.kit_vectors and not args.kit_native_output,
                    "explicit_policy_required")
            envelope = load_json(args.envelope)
            policy, basis = select_inputs(envelope, policy_id=args.policy_id, configuration=configuration())
            result = consume(envelope, policy=policy, accepted_basis=basis, registry=registry())
            code = 0 if result["outcome"] == "PRESERVED" else 2
        elif args.kit_vectors or args.kit_native_output:
            require(args.kit_vectors and args.kit_native_output and args.policy_id, "external_paths_and_policy_required")
            result = compare_external(args.kit_vectors, args.kit_native_output, args.policy_id)
            code = 0 if result["decision"]["outcome"] == "PRESERVED" else 2
        else:
            require(not args.policy_id, "unused_policy")
            result, code = run_suite(), 0
        print(json.dumps(result, sort_keys=True, indent=2, ensure_ascii=False, allow_nan=False))
        return code
    except (ContractError, KeyError, TypeError, ValueError, OSError) as exc:
        print(json.dumps({"schema_version": VERSION, "outcome": "UNVERIFIABLE", "guarantee": None,
                          "reason": str(exc)}, sort_keys=True))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
