from __future__ import annotations

import hashlib
import json
from pathlib import Path, PurePosixPath
import subprocess
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
LANE = ROOT / "evidence" / "external-systems" / "trustless-ai" / "v0"
STARTING_MAIN = "3d74bdb944cd9b8b625fe7c8f08dbb266fc7d5dc"
V0_COMMIT = "98ccba804c725777e155ad2f1a07bae49754376b"
V0_TREE = "c2449cb3a52e60c4f93e3c8a3a35c086c47f2d63"

REPOSITORIES = {
    "agent-contracts-examples": {
        "default_branch": "main",
        "commit": "60855b200745d2f6dfd24b266f95ca92ce102ed2",
        "tree": "9fe8df13e3194501ef49eac5fe94dbe8cb47a11b",
    },
    "agent-ercs": {
        "default_branch": "main",
        "commit": "01283ca57305f915afb560d23359a27fd748eb5a",
        "tree": "89d9d25f99b926e944f37920103191893a563a5b",
    },
    "ccip-router": {
        "default_branch": "main",
        "commit": "6bd66611b88a4751a0acc233c718aa9a13294de4",
        "tree": "22ca5dc999600e223b0625f3eaa4c1f44ab29aa3",
    },
    "primitives": {
        "default_branch": "main",
        "commit": "6b39e9540d4bd0a78decb588c0a8e328c303f208",
        "tree": "d1821bf1547632d531233007195241002b5459ee",
    },
    "recompute-kit": {
        "default_branch": "main",
        "commit": "d21bcc718bf505b46c4d32d7f3c858dff9d3e8bc",
        "tree": "ec51253674f7c145c4dfacc6fb58d3db9442a4a2",
    },
    "trustless-agent-substrate": {
        "default_branch": "feature/tas-poc",
        "commit": "a344ef80f7c52c03b9183814d1874b8054639c3e",
        "tree": "f3455e200fb4edc93452ff988832631058dfad3a",
    },
    "verify-layer": {
        "default_branch": "main",
        "commit": "84afc4b738dc37269089c858404eed8086435f5d",
        "tree": "d6b8e0022938f2197d7f54a68f3dff04ff689343",
    },
}

CASE_CONTRACT = {
    "TAI-001": ("INCLUDED", "verification_authority_class", "VIOLATED"),
    "TAI-002": ("INCLUDED", "anchor_security_authority_class", "VIOLATED"),
    "TAI-003": ("INCLUDED", "profile_authorized_repository_identity", "VIOLATED"),
    "TAI-004": ("INCLUDED", "as_of_chain_authority", "VIOLATED"),
    "TAI-005": ("INCLUDED", "claim_to_observation_binding", "VIOLATED"),
    "TAI-006": ("DEFERRED_NO_CURRENT_SOURCE_SURFACE", "nested_semantic_recomputation_requirement", "UNVERIFIABLE"),
    "TAI-007": ("INCLUDED", "profile_authorized_repository_file_identity", "PRESERVED"),
}
LIVE_STATUS = {
    "LIVE-001": "LIVE_REPRODUCED",
    "LIVE-002": "LIVE_REPRODUCED",
    "LIVE-003": "LIVE_REPRODUCED",
    "LIVE-004": "LIVE_REPRODUCTION_REQUIRES_CREDENTIALS",
    "LIVE-005": "LIVE_REPRODUCTION_UNAVAILABLE_LOCAL_RUNTIME",
    "LIVE-006": "DEFERRED_NO_CURRENT_SOURCE_SURFACE",
}
ALLOWED_OUTCOMES = {"PRESERVED", "VIOLATED", "UNVERIFIABLE"}
REQUIRED_CASE_FIELDS = {
    "case_id", "status", "title", "source_refs", "raw_observed_state",
    "state_before", "state_after", "weak_observation", "protected_relation",
    "protected_scope", "expected_outcome", "rationale", "authority_boundary",
    "system_property_class",
}


class AuditValidationError(ValueError):
    """A fail-closed deterministic case-study validation failure."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AuditValidationError(message)


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def git_blob_sha1(raw: bytes) -> str:
    header = f"blob {len(raw)}\0".encode("ascii")
    return hashlib.sha1(header + raw).hexdigest()


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        require(key not in result, f"DUPLICATE_JSON_KEY:{key}")
        result[key] = value
    return result


def load_json(path: Path, authored: bool = True) -> Any:
    require(path.is_file(), f"MISSING_FILE:{path}")
    raw = path.read_bytes()
    if authored:
        require(raw and not raw.startswith(b"\xef\xbb\xbf"), f"INVALID_TEXT_FRAMING:{path}")
        require(b"\r" not in raw and raw.endswith(b"\n"), f"INVALID_TEXT_FRAMING:{path}")
    try:
        return json.loads(raw.decode("utf-8"), object_pairs_hook=_reject_duplicate_keys)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise AuditValidationError(f"MALFORMED_JSON:{path}:{exc}") from exc


def _safe_relative_path(value: Any) -> str:
    require(isinstance(value, str) and value, "INVALID_INVENTORY_PATH")
    require("\\" not in value, f"NON_POSIX_INVENTORY_PATH:{value}")
    pure = PurePosixPath(value)
    require(not pure.is_absolute() and ".." not in pure.parts, f"UNSAFE_INVENTORY_PATH:{value}")
    require(pure.parts[0] in {"sources", "live"}, f"OUT_OF_SCOPE_INVENTORY_PATH:{value}")
    return value


def validate_inventory(lane: Path) -> tuple[dict[str, Any], dict[str, dict[str, Any]]]:
    inventory = load_json(lane / "source-inventory.json")
    require(isinstance(inventory, dict), "MALFORMED_SOURCE_INVENTORY")
    require(inventory.get("schema") == "prf-trustless-ai-source-inventory.v0", "WRONG_INVENTORY_SCHEMA")
    require(inventory.get("repositories") == REPOSITORIES, "SOURCE_REPOSITORY_IDENTITY_MISMATCH")
    entries = inventory.get("artifacts")
    require(isinstance(entries, list), "MALFORMED_SOURCE_ENTRIES")
    paths: list[str] = []
    by_path: dict[str, dict[str, Any]] = {}
    for entry in entries:
        require(isinstance(entry, dict), "MALFORMED_SOURCE_ENTRY")
        path = _safe_relative_path(entry.get("relative_path"))
        require(path not in by_path, f"DUPLICATE_SOURCE_PATH:{path}")
        paths.append(path)
        by_path[path] = entry
        raw = (lane / path).read_bytes() if (lane / path).is_file() else None
        require(raw is not None, f"MISSING_SOURCE:{path}")
        require(entry.get("byte_length") == len(raw), f"SOURCE_BYTE_LENGTH_MISMATCH:{path}")
        require(entry.get("sha256") == sha256_bytes(raw), f"SOURCE_SHA256_MISMATCH:{path}")
        if path.startswith("sources/"):
            require(entry.get("classification") == "SOURCE_GIT_BLOB", f"WRONG_SOURCE_CLASS:{path}")
            repo = path.split("/", 2)[1]
            require(entry.get("repository") == f"trustless-ai/{repo}", f"SOURCE_REPO_MISMATCH:{path}")
            require(entry.get("commit") == REPOSITORIES[repo]["commit"], f"SOURCE_COMMIT_MISMATCH:{path}")
            require(entry.get("tree") == REPOSITORIES[repo]["tree"], f"SOURCE_TREE_MISMATCH:{path}")
            require(entry.get("git_blob_sha1") == git_blob_sha1(raw), f"SOURCE_BLOB_MISMATCH:{path}")
        else:
            require(entry.get("git_blob_sha1") is None, f"LIVE_PAYLOAD_HAS_GIT_BLOB:{path}")
    require(paths == sorted(paths), "NON_CANONICAL_SOURCE_INVENTORY_ORDER")
    actual = sorted(
        path.relative_to(lane).as_posix()
        for directory in (lane / "sources", lane / "live")
        for path in directory.rglob("*")
        if path.is_file()
    )
    require(actual == paths, "SOURCE_CLOSED_UNIVERSE_MISMATCH")
    require(inventory.get("artifact_count") == len(entries), "SOURCE_COUNT_MISMATCH")
    require(inventory.get("total_bytes") == sum(item["byte_length"] for item in entries), "SOURCE_BYTES_MISMATCH")
    return inventory, by_path


def _validate_case_semantic_invariants(case: dict[str, Any]) -> None:
    case_id = case["case_id"]
    if case_id == "TAI-001":
        require(case["state_before"].get("header_state_root_authority") == "RPC_TRUSTED", "TAI001_RPC_AUTHORITY_CHANGED")
        require(case["state_after"].get("header_state_root_authority") == "CONSENSUS_RE_DERIVED", "TAI001_HEADER_AUTHORITY_CHANGED")
    elif case_id == "TAI-002":
        require(case["state_before"].get("anchor_tier") == "ROLLUP_TESTNET_ANCHORED", "TAI002_TESTNET_TIER_CHANGED")
        require(case["state_after"].get("anchor_tier") == "ETHEREUM_MAINNET_ANCHORED", "TAI002_STRONGER_TIER_CHANGED")
        require(case["raw_observed_state"].get("bitcoin_ots_for_exact_object") == "NOT_ESTABLISHED", "TAI002_BITCOIN_AUTHORITY_FABRICATED")
    elif case_id == "TAI-003":
        before = case["state_before"]
        after = case["state_after"]
        require(before.get("profile_selected_repository") != after.get("profile_selected_repository"), "TAI003_PROFILE_IDENTITY_COLLAPSED")
        require(case["weak_observation"].get("returned_bytes") == "SAME", "TAI003_WEAK_OBSERVATION_CHANGED")
    elif case_id == "TAI-004":
        require(case["state_before"].get("selector") == "EXACT_BLOCK_HASH", "TAI004_EXACT_AS_OF_REMOVED")
        require(case["state_before"].get("requireCanonical") is True, "TAI004_CANONICALITY_REMOVED")
        require(case["state_after"].get("fallback") == "NUMBER_ONLY_OR_CURRENT_STATE", "TAI004_COUNTERFACTUAL_CHANGED")
    elif case_id == "TAI-005":
        require(case["state_before"].get("observation_status") == "OBSERVATION_BOUND_TO_DECLARED_INPUT_OUTPUT_FIELDS", "TAI005_OBSERVATION_BINDING_CHANGED")
        require(case["state_after"].get("observation_status") == "OBSERVATION_BINDING_ABSENT_OR_UNAVAILABLE", "TAI005_UNBOUND_STATE_CHANGED")
    elif case_id == "TAI-006":
        require(case["state_before"].get("inner_semantics") == "NOT_REPRODUCED_BY_A_DEFINED_OUTER_RULE", "TAI006_NESTED_BYTES_UPGRADED")
        require(case["raw_observed_state"].get("general_nested_semantic_rule") == "NOT_FOUND", "TAI006_SOURCE_SURFACE_FABRICATED")
    elif case_id == "TAI-007":
        require(case["state_before"].get("base64_transport_line_endings") == "LF", "TAI007_CONTROL_BEFORE_CHANGED")
        require(case["state_after"].get("base64_transport_line_endings") == "CRLF", "TAI007_CONTROL_AFTER_CHANGED")
        require(case["state_before"].get("decoded_file_bytes") == case["state_after"].get("decoded_file_bytes"), "TAI007_PROTECTED_BYTES_CHANGED")


def validate_cases(lane: Path, source_paths: set[str]) -> dict[str, Any]:
    value = load_json(lane / "cases.json")
    require(value.get("schema") == "prf-trustless-ai-deterministic-cases.v0", "WRONG_CASE_SCHEMA")
    authority = value.get("authority")
    require(authority == {
        "starting_prf_main": STARTING_MAIN,
        "prf_v0_commit": V0_COMMIT,
        "prf_v0_tree": V0_TREE,
    }, "CASE_AUTHORITY_MISMATCH")
    cases = value.get("cases")
    require(isinstance(cases, list), "MALFORMED_CASES")
    require([case.get("case_id") for case in cases] == list(CASE_CONTRACT), "CASE_SET_OR_ORDER_MISMATCH")
    for case in cases:
        require(isinstance(case, dict) and set(case) == REQUIRED_CASE_FIELDS, f"MALFORMED_CASE:{case.get('case_id')}")
        case_id = case["case_id"]
        expected_status, expected_relation, expected_outcome = CASE_CONTRACT[case_id]
        require(case["status"] == expected_status, f"CASE_STATUS_MISMATCH:{case_id}")
        require(isinstance(case["weak_observation"], dict) and case["weak_observation"], f"WEAK_OBSERVATION_MISSING:{case_id}")
        require(case["protected_relation"] == expected_relation, f"PROTECTED_RELATION_MISMATCH:{case_id}")
        require(case["protected_relation"] not in json.dumps(case["weak_observation"], sort_keys=True), f"WEAK_OBSERVATION_SUBSTITUTED:{case_id}")
        require(isinstance(case["protected_scope"], list) and case["protected_scope"], f"PROTECTED_SCOPE_MISSING:{case_id}")
        require(case["expected_outcome"] in ALLOWED_OUTCOMES, f"UNSUPPORTED_EXPECTED_OUTCOME:{case_id}")
        require(case["expected_outcome"] == expected_outcome, f"EXPECTED_OUTCOME_MISMATCH:{case_id}")
        require(isinstance(case["authority_boundary"], str) and case["authority_boundary"], f"AUTHORITY_BOUNDARY_MISSING:{case_id}")
        refs = case["source_refs"]
        require(isinstance(refs, list) and refs and len(refs) == len(set(refs)), f"SOURCE_REFS_INVALID:{case_id}")
        for ref in refs:
            require(ref in source_paths, f"SOURCE_REF_MISSING:{case_id}:{ref}")
        _validate_case_semantic_invariants(case)
    require(any(case["expected_outcome"] == "PRESERVED" for case in cases), "PRESERVED_CONTROL_MISSING")
    require(any(case["expected_outcome"] == "VIOLATED" for case in cases), "VIOLATED_CASE_MISSING")
    require(any(case["expected_outcome"] == "UNVERIFIABLE" for case in cases), "UNVERIFIABLE_CASE_MISSING")
    return value


def validate_results(lane: Path, cases: dict[str, Any]) -> dict[str, Any]:
    results = load_json(lane / "case-results.json")
    require(results.get("schema") == "prf-trustless-ai-deterministic-case-results.v0", "WRONG_RESULTS_SCHEMA")
    require(results.get("method") == "SOURCE_AND_PUBLIC_EVIDENCE_DETERMINISTIC_COMPARISON", "WRONG_RESULTS_METHOD")
    require(results.get("model_calls") == 0, "MODEL_CALLS_NOT_ZERO")
    expected_by_id = {case["case_id"]: case for case in cases["cases"]}
    rows = results.get("results")
    require(isinstance(rows, list) and [row.get("case_id") for row in rows] == list(CASE_CONTRACT), "RESULT_SET_MISMATCH")
    class_counts: dict[str, int] = {}
    for row in rows:
        case_id = row["case_id"]
        require(row.get("deterministic_outcome") == expected_by_id[case_id]["expected_outcome"], f"RESULT_OUTCOME_MISMATCH:{case_id}")
        require(row.get("finding_classes") == expected_by_id[case_id]["system_property_class"], f"RESULT_CLASS_MISMATCH:{case_id}")
        require(isinstance(row.get("finding"), str) and row["finding"], f"RESULT_FINDING_MISSING:{case_id}")
        for classification in row["finding_classes"]:
            class_counts[classification] = class_counts.get(classification, 0) + 1
    expected_counts = {
        "SOURCE_BACKED_SEMANTIC_DISTINCTION": class_counts.get("SOURCE_BACKED_SEMANTIC_DISTINCTION", 0),
        "SOURCE_BACKED_AUTHORITY_OVERCLAIM": class_counts.get("SOURCE_BACKED_AUTHORITY_OVERCLAIM", 0),
        "LIVE_REPRODUCED_RELATION_DISTINCTION": class_counts.get("LIVE_REPRODUCED_RELATION_DISTINCTION", 0),
        "POSITIVE_FAIL_CLOSED_PROPERTY": class_counts.get("POSITIVE_FAIL_CLOSED_PROPERTY", 0),
        "PREVIOUS_GAP_REPAIRED": class_counts.get("PREVIOUS_GAP_REPAIRED", 0),
        "UNVERIFIABLE_OR_DEFERRED": class_counts.get("DEFERRED_NO_CURRENT_SOURCE_SURFACE", 0),
    }
    require(results.get("finding_counts") == expected_counts, "FINDING_COUNTS_MISMATCH")
    return results


def validate_live_summary(lane: Path, source_paths: set[str]) -> dict[str, Any]:
    value = load_json(lane / "live-reproduction-summary.json")
    require(value.get("schema") == "prf-trustless-ai-live-reproduction-summary.v0", "WRONG_LIVE_SCHEMA")
    require(value.get("credentials_used") is False, "PRIVATE_CREDENTIAL_USE_DECLARED")
    require(value.get("model_calls") == 0, "LIVE_MODEL_CALLS_NOT_ZERO")
    checks = value.get("checks")
    require(isinstance(checks, list) and [item.get("check_id") for item in checks] == list(LIVE_STATUS), "LIVE_CHECK_SET_MISMATCH")
    for check in checks:
        check_id = check["check_id"]
        require(check.get("status") == LIVE_STATUS[check_id], f"LIVE_STATUS_MISMATCH:{check_id}")
        require(isinstance(check.get("boundary"), str) and check["boundary"], f"LIVE_BOUNDARY_MISSING:{check_id}")
        refs = check.get("evidence")
        require(isinstance(refs, list) and refs, f"LIVE_EVIDENCE_MISSING:{check_id}")
        for ref in refs:
            require(ref in source_paths, f"LIVE_SOURCE_REF_MISSING:{check_id}:{ref}")
    receipt = load_json(lane / "live/base-sepolia-attestation-receipt.response.json", authored=False)
    rpc_result = receipt.get("result")
    require(isinstance(rpc_result, dict) and rpc_result.get("status") == "0x1", "LIVE_RECEIPT_NOT_SUCCESSFUL")
    require(rpc_result.get("blockHash") == "0x148626a43a7df72931ed965d2d8d7f63920d5b021f970b4662627b76ecdb26ba", "LIVE_BLOCK_BINDING_MISMATCH")
    require(any(
        log.get("topics", [None, None])[1] == "0x096e9df2fccbaf49525a22d3537670ec83746157846f0c25509a6483fe1d0a91"
        for log in rpc_result.get("logs", []) if isinstance(log, dict) and len(log.get("topics", [])) > 1
    ), "LIVE_COMMITMENT_EVENT_MISSING")
    return value


def validate_record_and_report(lane: Path, inventory: dict[str, Any]) -> tuple[dict[str, Any], str]:
    record = load_json(lane / "evidence-record.json")
    require(record.get("schema") == "prf-trustless-ai-deterministic-evidence-record.v0", "WRONG_RECORD_SCHEMA")
    require(record.get("method") == "ZERO_MODEL_SOURCE_AND_PUBLIC_EVIDENCE_AUDIT", "WRONG_AUDIT_METHOD")
    require(record.get("authority") == {
        "starting_prf_main": STARTING_MAIN,
        "frozen_prf_v0_commit": V0_COMMIT,
        "frozen_prf_v0_tree": V0_TREE,
    }, "EVIDENCE_AUTHORITY_MISMATCH")
    require(record.get("trustless_ai_repositories") == {key: value["commit"] for key, value in REPOSITORIES.items()}, "EVIDENCE_REPOSITORY_BINDING_MISMATCH")
    bindings = record.get("bindings")
    expected_bindings = {
        "source_inventory_sha256": sha256_bytes((lane / "source-inventory.json").read_bytes()),
        "cases_sha256": sha256_bytes((lane / "cases.json").read_bytes()),
        "case_results_sha256": sha256_bytes((lane / "case-results.json").read_bytes()),
        "live_reproduction_summary_sha256": sha256_bytes((lane / "live-reproduction-summary.json").read_bytes()),
        "report_sha256": sha256_bytes((lane / "REPORT.md").read_bytes()),
    }
    require(bindings == expected_bindings, "EVIDENCE_DIGEST_BINDING_MISMATCH")
    require(record.get("capture") == {
        "source_and_live_artifacts": inventory["artifact_count"],
        "source_and_live_bytes": inventory["total_bytes"],
        "model_calls": 0,
        "credentials_used": False,
        "chat_used_as_authority": False,
    }, "EVIDENCE_CAPTURE_SUMMARY_MISMATCH")
    report_raw = (lane / "REPORT.md").read_bytes()
    require(report_raw and b"\r" not in report_raw and report_raw.endswith(b"\n"), "REPORT_TEXT_FRAMING_INVALID")
    report = report_raw.decode("utf-8")
    for section in range(1, 13):
        require(f"## {section}." in report, f"REPORT_SECTION_MISSING:{section}")
    require("No LLM or model judgment is used in this audit." in report, "ZERO_MODEL_BOUNDARY_MISSING")
    require("Trustless AI is broken" not in report and "PRF found a vulnerability" not in report, "REPORT_OVERCLAIM")
    return record, sha256_bytes(report_raw)


def _git(root: Path, *args: str) -> str:
    completed = subprocess.run(["git", *args], cwd=root, capture_output=True, text=True)
    require(completed.returncode == 0, f"GIT_CHECK_FAILED:{' '.join(args)}:{completed.stderr.strip()}")
    return completed.stdout.strip()


def validate_git_authority(root: Path) -> None:
    require(_git(root, "rev-parse", "v0^{commit}") == V0_COMMIT, "FROZEN_V0_COMMIT_CHANGED")
    require(_git(root, "rev-parse", "v0^{tree}") == V0_TREE, "FROZEN_V0_TREE_CHANGED")
    protected = [
        "corpus/v0", "releases/v0", "adapters/v0", "spec/external-adapter-contract-v0.md",
        "evidence/external-evaluators/v0",
    ]
    completed = subprocess.run(
        ["git", "diff", "--quiet", STARTING_MAIN, "--", *protected], cwd=root,
    )
    require(completed.returncode == 0, "EXISTING_PRF_AUTHORITY_OR_EVIDENCE_CHANGED")


def validate_audit(lane: Path = LANE, repo_root: Path = ROOT, check_git: bool = True) -> dict[str, Any]:
    inventory, entries = validate_inventory(lane)
    cases = validate_cases(lane, set(entries))
    results = validate_results(lane, cases)
    live = validate_live_summary(lane, set(entries))
    record, report_sha = validate_record_and_report(lane, inventory)
    if check_git:
        validate_git_authority(repo_root)
    return {
        "inventory": inventory,
        "cases": cases,
        "results": results,
        "live": live,
        "record": record,
        "report_sha256": report_sha,
    }


def main() -> int:
    try:
        result = validate_audit()
    except AuditValidationError as exc:
        print(f"trustless-ai deterministic audit: FAIL ({exc})")
        return 1
    counts = result["results"]["finding_counts"]
    print(
        "trustless-ai deterministic audit: PASS "
        f"({len(result['cases']['cases'])} cases; "
        f"{result['inventory']['artifact_count']} artifacts; "
        f"{result['inventory']['total_bytes']} bytes; "
        f"source distinctions={counts['SOURCE_BACKED_SEMANTIC_DISTINCTION']}; "
        "model calls=0)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
