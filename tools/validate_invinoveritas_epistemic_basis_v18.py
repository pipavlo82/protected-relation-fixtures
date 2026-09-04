from __future__ import annotations

import hashlib
import json
from pathlib import Path, PurePosixPath
import subprocess
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
LANE = ROOT / "evidence" / "external-systems" / "invinoveritas" / "v18"
STARTING_MAIN = "d3f81f7fa8806135649a616a4b609fbb4f7eca44"
V0_COMMIT = "98ccba804c725777e155ad2f1a07bae49754376b"
V0_TREE = "c2449cb3a52e60c4f93e3c8a3a35c086c47f2d63"
PUBLIC_REPO = "babyblueviper1/invinoveritas"
PUBLIC_COMMIT = "3bdea4f08d7a399acd07c4e6d36e34dd38fadee8"
PUBLIC_TREE = "4f0d45ba90bde841b304477ecda86d7aac18da70"
EVENT_ID = "725eaec0331a0f08f5311fef3c6f85c5d7f080eec87bf12098682ab9bb924c87"
DECISION_REF = "sha256:55d9f7032dd271c495a0187d866ca45a9edd78d78a55b77cbd7405442bbc520d"
LEGACY_INTERPRETATION = "legacy pre-v18 / epistemic basis unknown"
ALLOWED_OUTCOMES = {"PRESERVED", "VIOLATED", "UNVERIFIABLE"}
LANE_REPOSITORY_PATH = "evidence/external-systems/invinoveritas/v18"


class InvinoVeritasValidationError(ValueError):
    """Fail-closed InvinoVeritas case-study validation failure."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise InvinoVeritasValidationError(message)


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def git_blob_sha1(raw: bytes) -> str:
    return hashlib.sha1(f"blob {len(raw)}\0".encode("ascii") + raw).hexdigest()


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        require(key not in result, f"DUPLICATE_JSON_KEY:{key}")
        result[key] = value
    return result


def load_json(path: Path, *, authored: bool = True) -> Any:
    require(path.is_file(), f"MISSING_FILE:{path}")
    raw = path.read_bytes()
    if authored:
        require(raw and not raw.startswith(b"\xef\xbb\xbf"), f"INVALID_TEXT_FRAMING:{path}")
        require(b"\r" not in raw and raw.endswith(b"\n"), f"INVALID_TEXT_FRAMING:{path}")
    try:
        return json.loads(raw.decode("utf-8"), object_pairs_hook=_reject_duplicate_keys)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise InvinoVeritasValidationError(f"MALFORMED_JSON:{path}:{exc}") from exc


def _safe_path(value: Any) -> str:
    require(isinstance(value, str) and value, "INVALID_INVENTORY_PATH")
    require("\\" not in value, f"NON_POSIX_PATH:{value}")
    path = PurePosixPath(value)
    require(not path.is_absolute() and ".." not in path.parts, f"UNSAFE_PATH:{value}")
    require(path.parts[0] in {"live", "sources"}, f"OUT_OF_SCOPE_PATH:{value}")
    return value


def validate_inventory(lane: Path) -> dict[str, Any]:
    inventory = load_json(lane / "source-inventory.json")
    require(inventory.get("schema") == "prf-invinoveritas-source-inventory.v0", "WRONG_INVENTORY_SCHEMA")
    expected_repo = {PUBLIC_REPO: {"default_branch": "main", "commit": PUBLIC_COMMIT, "tree": PUBLIC_TREE}}
    require(inventory.get("repositories") == expected_repo, "SOURCE_REPOSITORY_IDENTITY_MISMATCH")
    entries = inventory.get("artifacts")
    require(isinstance(entries, list), "MALFORMED_INVENTORY")
    paths: list[str] = []
    for entry in entries:
        require(isinstance(entry, dict), "MALFORMED_INVENTORY_ENTRY")
        relative = _safe_path(entry.get("relative_path"))
        require(relative not in paths, f"DUPLICATE_INVENTORY_PATH:{relative}")
        paths.append(relative)
        path = lane / relative
        require(path.is_file(), f"MISSING_CAPTURE:{relative}")
        raw = path.read_bytes()
        require(entry.get("byte_length") == len(raw), f"BYTE_LENGTH_MISMATCH:{relative}")
        require(entry.get("sha256") == sha256_bytes(raw), f"SHA256_MISMATCH:{relative}")
        if relative.startswith("sources/"):
            require(entry.get("classification") == "SOURCE_GIT_BLOB", f"WRONG_SOURCE_CLASS:{relative}")
            require(entry.get("repository") == PUBLIC_REPO, f"SOURCE_REPO_MISMATCH:{relative}")
            require(entry.get("commit") == PUBLIC_COMMIT, f"SOURCE_COMMIT_MISMATCH:{relative}")
            require(entry.get("tree") == PUBLIC_TREE, f"SOURCE_TREE_MISMATCH:{relative}")
            require(entry.get("git_blob_sha1") == git_blob_sha1(raw), f"SOURCE_BLOB_MISMATCH:{relative}")
        else:
            require(entry.get("git_blob_sha1") is None, f"LIVE_HAS_GIT_BLOB:{relative}")
    require(paths == sorted(paths), "NON_CANONICAL_INVENTORY_ORDER")
    actual = sorted(
        path.relative_to(lane).as_posix()
        for directory in (lane / "live", lane / "sources")
        for path in directory.rglob("*")
        if path.is_file()
    )
    require(paths == actual, "CAPTURE_CLOSED_UNIVERSE_MISMATCH")
    require(inventory.get("artifact_count") == len(entries), "ARTIFACT_COUNT_MISMATCH")
    require(inventory.get("total_bytes") == sum(item["byte_length"] for item in entries), "TOTAL_BYTES_MISMATCH")
    return inventory


def _checks(response: dict[str, Any], expected: bool, label: str) -> None:
    require(response.get("valid") is expected, f"{label}_VALID_MISMATCH")
    checks = response.get("checks")
    require(isinstance(checks, dict), f"{label}_CHECKS_MISSING")
    for name in ("id_integrity", "signature_valid", "decision_ref_recomputes"):
        require(checks.get(name) is expected, f"{label}_{name.upper()}_MISMATCH")


def validate_live_semantics(lane: Path) -> dict[str, Any]:
    live = lane / "live"
    retrieval = load_json(live / "v18-original-retrieval.response.json", authored=False)
    original_request = load_json(live / "v18-original-verify.request.json", authored=False)
    original_response = load_json(live / "v18-original-verify.response.json", authored=False)
    tampered_request = load_json(live / "v18-tampered-verify.request.json", authored=False)
    tampered_response = load_json(live / "v18-tampered-verify.response.json", authored=False)
    tamper_diff = load_json(live / "v18-tamper-diff.json", authored=False)
    event = retrieval.get("event")
    require(isinstance(event, dict) and event.get("id") == EVENT_ID, "V18_EVENT_ID_MISMATCH")
    require(original_request == {"event": event}, "ORIGINAL_REQUEST_NOT_EXACT_RETRIEVED_EVENT")
    original_payload = json.loads(event.get("content", ""), object_pairs_hook=_reject_duplicate_keys)
    require(original_payload.get("policy_version") == "invinoveritas.review.v18", "V18_POLICY_MISMATCH")
    require(original_payload.get("verdict") == "reject", "V18_VERDICT_MISMATCH")
    require("epistemic_basis" in original_payload and original_payload["epistemic_basis"] is None, "V18_NULL_BASIS_MISSING")
    require(original_payload.get("decision_ref") == DECISION_REF, "V18_DECISION_REF_MISMATCH")
    fields = original_payload.get("decision_ref_preimage_fields")
    require(isinstance(fields, list) and "epistemic_basis" in fields, "V18_BASIS_NOT_IN_PREIMAGE")
    rule = original_payload.get("decision_ref_preimage_rule")
    require(isinstance(rule, str) and "every name" in rule and "JSON null" in rule and "never omitted" in rule, "V18_PREIMAGE_RULE_MISMATCH")
    _checks(original_response, True, "V18_ORIGINAL")
    require(original_response.get("proof_payload") == original_payload, "ORIGINAL_RESPONSE_PAYLOAD_MISMATCH")

    tampered_event = tampered_request.get("event")
    require(isinstance(tampered_event, dict), "TAMPERED_EVENT_MISSING")
    require(set(tampered_event) == set(event), "TAMPERED_EVENT_SHAPE_CHANGED")
    for key in event:
        if key != "content":
            require(tampered_event[key] == event[key], f"TAMPER_CHANGED_OUTER_FIELD:{key}")
    tampered_payload = json.loads(tampered_event.get("content", ""), object_pairs_hook=_reject_duplicate_keys)
    changed = sorted(key for key in set(original_payload) | set(tampered_payload) if original_payload.get(key) != tampered_payload.get(key))
    require(changed == ["epistemic_basis"], "TAMPER_NOT_SINGLE_FIELD")
    require(tampered_payload.get("epistemic_basis") == "evidence_against", "TAMPER_BASIS_MISMATCH")
    require(tampered_payload.get("verdict") == original_payload.get("verdict") == "reject", "TAMPER_CHANGED_VERDICT")
    require(tampered_payload.get("decision_ref") == original_payload.get("decision_ref") == DECISION_REF, "TAMPER_CHANGED_DECISION_REF")
    require(tamper_diff.get("content_fields_changed") == ["epistemic_basis"], "TAMPER_DIFF_MISMATCH")
    require(tamper_diff.get("stored_decision_ref_unchanged") is True, "TAMPER_DIFF_REF_MISMATCH")
    _checks(tampered_response, False, "V18_TAMPER")
    require(tampered_response.get("proof_payload") == tampered_payload, "TAMPER_RESPONSE_PAYLOAD_MISMATCH")

    ledger = load_json(live / "v17-ledger-260.response.json", authored=False)
    legacy_request = load_json(live / "v17-ledger-260-verify.request.json", authored=False)
    legacy_response = load_json(live / "v17-ledger-260-verify.response.json", authored=False)
    require(ledger.get("entry") == 260, "LEGACY_LEDGER_ENTRY_MISMATCH")
    legacy_event = ledger.get("proof_event")
    require(isinstance(legacy_event, dict) and legacy_request == {"event": legacy_event}, "LEGACY_REQUEST_MISMATCH")
    legacy_payload = json.loads(legacy_event.get("content", ""), object_pairs_hook=_reject_duplicate_keys)
    require(legacy_payload.get("policy_version") == "invinoveritas.review.v17", "LEGACY_POLICY_MISMATCH")
    require("epistemic_basis" not in legacy_payload, "LEGACY_BASIS_BACKFILLED")
    legacy_fields = legacy_payload.get("decision_ref_preimage_fields")
    require(isinstance(legacy_fields, list) and "epistemic_basis" not in legacy_fields, "LEGACY_PREIMAGE_BACKFILLED")
    _checks(legacy_response, True, "LEGACY")
    require(legacy_response.get("proof_payload") == legacy_payload, "LEGACY_RESPONSE_PAYLOAD_MISMATCH")
    return {"original": original_payload, "tampered": tampered_payload, "legacy": legacy_payload}


def validate_metadata(lane: Path, inventory: dict[str, Any]) -> dict[str, Any]:
    cases = load_json(lane / "cases.json")
    results = load_json(lane / "case-results.json")
    live = load_json(lane / "live-reproduction-summary.json")
    upstream = load_json(lane / "upstream-report.json")
    record = load_json(lane / "evidence-record.json")
    case_list = cases.get("cases")
    require(isinstance(case_list, list) and len(case_list) == 1, "CASE_COUNT_MISMATCH")
    case = case_list[0]
    require(case.get("case_id") == "invinoveritas-epistemic-basis-commitment-v18", "CASE_ID_MISMATCH")
    require(case.get("weak_projection") == {"field": "verdict", "value": "reject", "before_equals_after": True}, "WEAK_PROJECTION_MISMATCH")
    require(case.get("protected_semantic_states") == ["reject/evidence_against", "reject/insufficient_evidence"], "PROTECTED_STATES_MISMATCH")
    require(case.get("protected_relation") == "epistemic_basis_decision_commitment", "PROTECTED_RELATION_MISMATCH")
    require(case.get("expected_outcome") in ALLOWED_OUTCOMES and case["expected_outcome"] == "VIOLATED", "EXPECTED_OUTCOME_MISMATCH")
    require(case.get("state_after", {}).get("commitment_status") == "COMMITMENT_VIOLATION_DETECTED", "COMMITMENT_CLASS_MISMATCH")
    inventory_paths = {item["relative_path"] for item in inventory["artifacts"]}
    require(set(case.get("source_refs", [])) == inventory_paths, "CASE_SOURCE_REFERENCES_MISMATCH")
    legacy = case.get("legacy_control", {})
    require(legacy.get("epistemic_basis_interpretation") == LEGACY_INTERPRETATION, "LEGACY_INTERPRETATION_UPGRADED")
    require(legacy.get("classification") == "LEGACY_COMPATIBILITY_CONTROL", "LEGACY_CONTROL_RECLASSIFIED")
    result = results.get("result", {})
    require(result.get("classification") == "COMMITMENT_VIOLATION_DETECTED", "RESULT_CLASSIFICATION_MISMATCH")
    require(result.get("underlying_reviewer_verdict_changed") is False, "TAMPER_RECAST_AS_VERDICT_CHANGE")
    require(result.get("v18_original", {}).get("preimage_fields_include_epistemic_basis") is True, "RESULT_V18_PREIMAGE_MISMATCH")
    require(result.get("v18_tamper", {}).get("decision_ref_recomputes") is False, "RESULT_TAMPER_NOT_DETECTED")
    result_legacy = result.get("legacy_v17_control", {})
    require(result_legacy.get("epistemic_basis_interpretation") == LEGACY_INTERPRETATION, "RESULT_LEGACY_INTERPRETATION_UPGRADED")
    require(result_legacy.get("classification") == "LEGACY_COMPATIBILITY_CONTROL", "RESULT_LEGACY_RECLASSIFIED")
    require(result_legacy.get("valid") is True and result_legacy.get("decision_ref_recomputes") is True, "RESULT_LEGACY_INVALID")
    require(live.get("offline_decision_ref_recomputation", {}).get("status") == "NOT_PERFORMED", "APPROXIMATE_OFFLINE_RECOMPUTATION_CLAIMED")
    require(all(item.get("status") == "LIVE_REPRODUCED" for item in live.get("checks", [])) and len(live.get("checks", [])) == 5, "LIVE_REPRODUCTION_STATUS_MISMATCH")
    require(upstream.get("resolution", {}).get("status") == "UPSTREAM_REPORTED_NOT_PUBLICLY_RESOLVED", "UPSTREAM_REPORT_UPGRADED")
    require(upstream.get("resolution", {}).get("binding_commit_reported") == "56e5999d", "UPSTREAM_BINDING_COMMIT_MISMATCH")
    require(upstream.get("resolution", {}).get("preview_docstring_commit_reported") == "0a40e39f", "UPSTREAM_FOLLOWUP_COMMIT_MISMATCH")
    reported = upstream.get("reported_facts_not_used_as_independent_public_authority", [])
    require(any("before it was included" in item and "decision_ref" in item and "commitment layer" in item for item in reported), "UPSTREAM_RECURSIVE_ARC_MISSING")
    global_search = upstream.get("resolution", {}).get("github_global_commit_prefix_search", {})
    require(global_search.get("56e5999d") == "NO_PUBLIC_RESULTS", "UPSTREAM_BINDING_GLOBAL_SEARCH_MISMATCH")
    require(global_search.get("0a40e39f") == "TWO_UNRELATED_PREFIX_COLLISIONS; NO_INVINO_VERITAS_RESULT", "UPSTREAM_FOLLOWUP_GLOBAL_SEARCH_MISMATCH")
    require(record.get("starting_prf_main") == STARTING_MAIN, "STARTING_MAIN_MISMATCH")
    require(record.get("frozen_v0") == {"commit": V0_COMMIT, "tree": V0_TREE}, "FROZEN_V0_IDENTITY_MISMATCH")
    require(record.get("public_source_authority", {}).get("commit") == PUBLIC_COMMIT, "RECORD_PUBLIC_COMMIT_MISMATCH")
    binding = record.get("artifact_inventory", {})
    require(binding.get("artifact_count") == inventory.get("artifact_count"), "RECORD_ARTIFACT_COUNT_MISMATCH")
    require(binding.get("total_bytes") == inventory.get("total_bytes"), "RECORD_TOTAL_BYTES_MISMATCH")
    require(binding.get("sha256") == sha256_bytes((lane / "source-inventory.json").read_bytes()), "RECORD_INVENTORY_DIGEST_MISMATCH")
    metadata = record.get("metadata_digests")
    require(isinstance(metadata, dict), "RECORD_METADATA_DIGESTS_MISSING")
    expected_metadata = {"README.md", "REPORT.md", "case-results.json", "cases.json", "live-reproduction-summary.json", "upstream-report.json"}
    require(set(metadata) == expected_metadata, "RECORD_METADATA_SET_MISMATCH")
    for name, digest in metadata.items():
        require(digest == sha256_bytes((lane / name).read_bytes()), f"RECORD_METADATA_DIGEST_MISMATCH:{name}")
    return {"cases": cases, "results": results, "live": live, "upstream": upstream, "record": record}


def _git(root: Path, *args: str) -> str:
    result = subprocess.run(["git", *args], cwd=root, check=False, capture_output=True, text=True)
    require(result.returncode == 0, f"GIT_COMMAND_FAILED:{' '.join(args)}:{result.stderr.strip()}")
    return result.stdout.strip()


def validate_git_boundaries(root: Path) -> None:
    require(_git(root, "rev-parse", "v0^{}") == V0_COMMIT, "FROZEN_V0_TAG_MOVED")
    require(_git(root, "rev-parse", "v0^{tree}") == V0_TREE, "FROZEN_V0_TREE_MOVED")
    record_path = f"{LANE_REPOSITORY_PATH}/evidence-record.json"
    introductions = _git(root, "log", "--diff-filter=A", "--format=%H", "--", record_path).splitlines()
    require(len(introductions) == 1, "EVIDENCE_INTRODUCTION_COMMIT_NOT_UNIQUE")
    introduction = introductions[0]
    parents = _git(root, "show", "-s", "--format=%P", introduction).split()
    require(parents == [STARTING_MAIN], "EVIDENCE_INTRODUCTION_PARENT_MISMATCH")
    ancestry = subprocess.run(
        ["git", "merge-base", "--is-ancestor", introduction, "HEAD"],
        cwd=root,
        check=False,
        capture_output=True,
    )
    require(ancestry.returncode == 0, "EVIDENCE_INTRODUCTION_NOT_IN_HEAD_ANCESTRY")
    introduced_lane_paths = _git(
        root, "ls-tree", "-r", "--name-only", introduction, "--", LANE_REPOSITORY_PATH
    ).splitlines()
    current_lane_paths = sorted(
        path.relative_to(root).as_posix()
        for path in (root / LANE_REPOSITORY_PATH).rglob("*")
        if path.is_file()
    )
    require(current_lane_paths == introduced_lane_paths, "EVIDENCE_LANE_MEMBERSHIP_DRIFT")
    expected_introduction_paths = set(introduced_lane_paths) | {
        "tests/test_invinoveritas_epistemic_basis_v18.py",
        "tools/validate_invinoveritas_epistemic_basis_v18.py",
    }
    changed_at_introduction = set(
        _git(root, "diff-tree", "--no-commit-id", "--name-only", "-r", introduction).splitlines()
    )
    require(changed_at_introduction == expected_introduction_paths, "EVIDENCE_INTRODUCTION_SCOPE_MISMATCH")
    for relative in introduced_lane_paths:
        blob = subprocess.run(
            ["git", "cat-file", "blob", f"{introduction}:{relative}"],
            cwd=root,
            check=False,
            capture_output=True,
        )
        require(blob.returncode == 0, f"EVIDENCE_INTRODUCTION_BLOB_MISSING:{relative}")
        require(blob.stdout == (root / relative).read_bytes(), f"EVIDENCE_DRIFT_AFTER_INTRODUCTION:{relative}")


def validate_case_study(
    lane: Path = LANE,
    *,
    repo_root: Path = ROOT,
    check_git: bool = True,
) -> dict[str, Any]:
    inventory = validate_inventory(lane)
    semantic = validate_live_semantics(lane)
    metadata = validate_metadata(lane, inventory)
    if check_git:
        validate_git_boundaries(repo_root)
    return {"inventory": inventory, "semantic": semantic, **metadata}


def main() -> int:
    try:
        result = validate_case_study()
    except InvinoVeritasValidationError as exc:
        print(f"INVINO_VERITAS_V18_CASE_STUDY_FAIL: {exc}")
        return 1
    print("INVINO_VERITAS_V18_CASE_STUDY_PASS")
    print(f"artifacts={result['inventory']['artifact_count']} bytes={result['inventory']['total_bytes']}")
    print("v18_original=VALID v18_tamper=COMMITMENT_VIOLATION_DETECTED")
    print("legacy_v17=VALID epistemic_basis=UNKNOWN")
    print("upstream_commits=UPSTREAM_REPORTED_NOT_PUBLICLY_RESOLVED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
