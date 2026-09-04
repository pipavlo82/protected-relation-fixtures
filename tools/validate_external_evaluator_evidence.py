from __future__ import annotations

import hashlib
import json
from pathlib import Path, PurePosixPath
import subprocess
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
EVIDENCE_ROOT = ROOT / "evidence" / "external-evaluators" / "v0"
INVENTORY_PATH = EVIDENCE_ROOT / "payload-inventory.json"
RECORD_PATH = EVIDENCE_ROOT / "evidence-record.json"
MATRIX_PATH = EVIDENCE_ROOT / "first-run-matrix.json"

V0_COMMIT = "98ccba804c725777e155ad2f1a07bae49754376b"
V0_TREE = "c2449cb3a52e60c4f93e3c8a3a35c086c47f2d63"
ADAPTER_COMMIT = "cf39a37d66222522368e719e3910c27a3eab31dd"
EVALUATOR_OUTPUT_SCHEMA_SHA256 = "60c3c89bf2ae7d5d406c4449da5e3de728cd37c9ab3749038b7da30193a33fff"
RESPONSE_SCHEMA_SHA256 = "a8557965c090cb8e6d1a4dbc0e2b7cd44832e1b16dd2021d63a92729aaab0a7a"
ORACLE_SHA256 = "8fa93a5ef4a61c3a7d80c8951c131e694d4947f16a9f38c9c813dd0a29a0b6e5"

CLASSIFICATIONS = (
    "MATCH",
    "UNSAFE_FALSE_PRESERVATION",
    "UNSAFE_UNVERIFIABLE_UPGRADE",
    "FALSE_VIOLATION",
    "PRESERVATION_NOT_ESTABLISHED",
    "VIOLATION_NOT_ESTABLISHED",
    "UNVERIFIABLE_MISCLASSIFIED_AS_VIOLATION",
)
CHALLENGE_IDS = tuple(f"prf-{index:03d}" for index in range(1, 7))
COMPARABLE_EXPERIMENTS = (
    "qwen2.5-3b-post-wrapper-repair",
    "qwen2.5-coder-7b",
    "llama3.1-8b",
)
ALL_EXPERIMENTS = (
    "qwen2.5-3b-pre-wrapper-repair",
    *COMPARABLE_EXPERIMENTS,
)

EXPERIMENT_SPECS: dict[str, dict[str, Any]] = {
    "qwen2.5-3b-pre-wrapper-repair": {
        "phase": "PRE_WRAPPER_REPAIR",
        "comparable": False,
        "provider": "local-ollama-wsl",
        "model": "qwen2.5:3b-instruct",
        "model_id": "357c53fb659c",
        "model_blob_digest": "sha256:5ee4f07cdb9beadbbb293e85803c569b01bd37ed059d2715faa7bb405f31caa6",
        "no_retries": None,
        "capture_before_scoring": None,
    },
    "qwen2.5-3b-post-wrapper-repair": {
        "phase": "POST_WRAPPER_REPAIR",
        "comparable": True,
        "provider": "local-wsl-ollama",
        "model": "qwen2.5:3b-instruct",
        "model_id": "357c53fb659c",
        "model_blob_digest": "sha256:5ee4f07cdb9beadbbb293e85803c569b01bd37ed059d2715faa7bb405f31caa6",
        "no_retries": True,
        "capture_before_scoring": True,
    },
    "qwen2.5-coder-7b": {
        "phase": "POST_WRAPPER_REPAIR",
        "comparable": True,
        "provider": "local-wsl-ollama",
        "model": "qwen2.5-coder:7b",
        "model_id": "dae161e27b0e",
        "model_blob_digest": "sha256:60e05f2100071479f596b964f89f510f057ce397ea22f2833a0cfe029bfc2463",
        "no_retries": True,
        "capture_before_scoring": True,
    },
    "llama3.1-8b": {
        "phase": "POST_WRAPPER_REPAIR",
        "comparable": True,
        "provider": "local-wsl-ollama",
        "model": "llama3.1:8b",
        "model_id": "46e0c10c039e",
        "model_blob_digest": "sha256:667b0c1932bc6ffc593ed1d03f895bf2dc8dc6df21db3042284a6f4416b06a29",
        "no_retries": True,
        "capture_before_scoring": True,
    },
}


class EvidenceValidationError(ValueError):
    """A fail-closed external-evaluator evidence validation error."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise EvidenceValidationError(message)


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def sha256_path(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        require(key not in result, f"DUPLICATE_JSON_KEY:{key}")
        result[key] = value
    return result


def load_json(path: Path) -> Any:
    require(path.is_file(), f"MISSING_EVIDENCE_FILE:{path}")
    raw = path.read_bytes()
    require(raw and not raw.startswith(b"\xef\xbb\xbf"), f"INVALID_JSON_FRAMING:{path}")
    require(b"\r" not in raw and raw.endswith(b"\n"), f"INVALID_JSON_FRAMING:{path}")
    try:
        return json.loads(raw.decode("utf-8"), object_pairs_hook=_reject_duplicate_keys)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise EvidenceValidationError(f"MALFORMED_EVIDENCE_JSON:{path}:{exc}") from exc


def _safe_payload_path(value: Any) -> str:
    require(isinstance(value, str) and value, "INVALID_INVENTORY_PATH")
    require("\\" not in value, f"NON_POSIX_INVENTORY_PATH:{value}")
    pure = PurePosixPath(value)
    require(not pure.is_absolute() and ".." not in pure.parts, f"UNSAFE_INVENTORY_PATH:{value}")
    require(pure.parts and pure.parts[0] == "first-runs", f"OUT_OF_SCOPE_INVENTORY_PATH:{value}")
    return value


def validate_payload_inventory(evidence_root: Path) -> tuple[dict[str, Any], dict[str, dict[str, Any]]]:
    inventory_path = evidence_root / "payload-inventory.json"
    inventory = load_json(inventory_path)
    require(isinstance(inventory, dict), "MALFORMED_PAYLOAD_INVENTORY")
    require(
        set(inventory) == {"schema", "entries", "total_files", "total_bytes"},
        "MALFORMED_PAYLOAD_INVENTORY_FIELDS",
    )
    require(
        inventory["schema"] == "protected-relation-external-evaluator-payload-inventory.v0",
        "WRONG_PAYLOAD_INVENTORY_SCHEMA",
    )
    entries = inventory["entries"]
    require(isinstance(entries, list), "MALFORMED_PAYLOAD_INVENTORY_ENTRIES")
    paths: list[str] = []
    by_path: dict[str, dict[str, Any]] = {}
    for entry in entries:
        require(isinstance(entry, dict), "MALFORMED_PAYLOAD_INVENTORY_ENTRY")
        require(set(entry) == {"path", "byte_length", "sha256"}, "MALFORMED_PAYLOAD_INVENTORY_ENTRY")
        path = _safe_payload_path(entry["path"])
        require(path not in by_path, f"DUPLICATE_INVENTORY_PATH:{path}")
        require(isinstance(entry["byte_length"], int) and entry["byte_length"] >= 0, f"INVALID_LENGTH:{path}")
        require(
            isinstance(entry["sha256"], str)
            and len(entry["sha256"]) == 64
            and all(char in "0123456789abcdef" for char in entry["sha256"]),
            f"INVALID_SHA256:{path}",
        )
        paths.append(path)
        by_path[path] = entry
    require(paths == sorted(paths), "NON_CANONICAL_INVENTORY_ORDER")
    require(len(paths) == len(set(paths)), "DUPLICATE_INVENTORY_PATH")
    actual_paths = sorted(
        path.relative_to(evidence_root).as_posix()
        for path in (evidence_root / "first-runs").rglob("*")
        if path.is_file()
    )
    require(actual_paths == paths, "PAYLOAD_CLOSED_UNIVERSE_MISMATCH")
    for path, entry in by_path.items():
        raw = (evidence_root / path).read_bytes()
        require(len(raw) == entry["byte_length"], f"PAYLOAD_BYTE_LENGTH_MISMATCH:{path}")
        require(sha256_bytes(raw) == entry["sha256"], f"PAYLOAD_SHA256_MISMATCH:{path}")
    require(inventory["total_files"] == len(entries), "PAYLOAD_TOTAL_FILES_MISMATCH")
    require(
        inventory["total_bytes"] == sum(entry["byte_length"] for entry in entries),
        "PAYLOAD_TOTAL_BYTES_MISMATCH",
    )
    return inventory, by_path


def _capture_configuration(bundle_root: Path, capture: dict[str, Any]) -> dict[str, Any]:
    if "configuration" in capture:
        config = capture["configuration"]
    else:
        config = load_json(bundle_root / "metadata" / "evaluator-config.json")
    require(isinstance(config, dict), "MALFORMED_CAPTURE_CONFIGURATION")
    return config


def _validate_capture(bundle_root: Path, experiment_id: str) -> dict[str, Any]:
    spec = EXPERIMENT_SPECS[experiment_id]
    capture = load_json(bundle_root / "capture-summary.json")
    require(isinstance(capture, dict), f"MALFORMED_CAPTURE_SUMMARY:{experiment_id}")
    require(capture.get("capture_complete") is True, f"INCOMPLETE_CAPTURE:{experiment_id}")
    require(capture.get("model_calls") == 6, f"WRONG_MODEL_CALL_COUNT:{experiment_id}")
    require(capture.get("one_call_per_challenge") is True, f"NOT_ONE_CALL_PER_CHALLENGE:{experiment_id}")
    require(capture.get("no_conversation_memory") is True, f"CONVERSATION_MEMORY_NOT_DISABLED:{experiment_id}")
    if spec["no_retries"] is True:
        require(capture.get("no_retries") is True, f"NO_RETRY_EVIDENCE_MISSING:{experiment_id}")
    if spec["capture_before_scoring"] is True:
        require(capture.get("scoring_performed") is False, f"CAPTURE_BEFORE_SCORING_NOT_EVIDENCED:{experiment_id}")
    config = _capture_configuration(bundle_root, capture)
    aliases = {
        "provider": config.get("provider"),
        "ollama_version": config.get("ollama_version"),
        "model": config.get("model"),
        "model_id": config.get("model_id"),
        "model_blob_digest": config.get("model_blob_digest"),
    }
    for field in ("provider", "model", "model_id", "model_blob_digest"):
        require(aliases[field] == spec[field], f"MODEL_IDENTITY_MISMATCH:{experiment_id}:{field}")
    require(aliases["ollama_version"] == "0.15.2", f"RUNTIME_IDENTITY_MISMATCH:{experiment_id}")
    leakage = load_json(bundle_root / "metadata" / "oracle-leakage-check.json")
    require(leakage.get("status") == "PASS", f"ORACLE_LEAKAGE_CHECK_NOT_PASS:{experiment_id}")
    require(leakage.get("requests_checked") == 6, f"ORACLE_LEAKAGE_REQUEST_COUNT_MISMATCH:{experiment_id}")
    require(leakage.get("answer_bearing_markers_found") == 0, f"ORACLE_LEAKAGE_DETECTED:{experiment_id}")
    return {"capture": capture, "config": aliases, "leakage": leakage}


def _oracle_outcomes(repo_root: Path) -> dict[str, str]:
    path = repo_root / "corpus" / "v0" / "oracle" / "expected-results.json"
    require(sha256_path(path) == ORACLE_SHA256, "FROZEN_ORACLE_IDENTITY_MISMATCH")
    oracle = load_json(path)
    outcomes = {key: value["semantic_outcome"] for key, value in oracle["results"].items()}
    require(tuple(sorted(outcomes)) == CHALLENGE_IDS, "FROZEN_ORACLE_COVERAGE_MISMATCH")
    return outcomes


def _derive_model_matrix(
    evidence_root: Path,
    experiment_id: str,
    oracle_outcomes: dict[str, str],
) -> dict[str, Any]:
    bundle = evidence_root / "first-runs" / experiment_id
    result_path = bundle / "final-results.json"
    final = load_json(result_path)
    score = load_json(bundle / "score-report.json")
    rows = final.get("rows")
    require(isinstance(rows, list) and len(rows) == 6, f"SOURCE_RESULT_COVERAGE_MISMATCH:{experiment_id}")
    require(
        [row.get("challenge_id") for row in rows] == list(CHALLENGE_IDS),
        f"SOURCE_RESULT_ORDER_OR_ID_MISMATCH:{experiment_id}",
    )
    score_details = {row["challenge_id"]: row for row in score.get("details", [])}
    require(tuple(sorted(score_details)) == CHALLENGE_IDS, f"SOURCE_SCORE_COVERAGE_MISMATCH:{experiment_id}")
    observations: list[dict[str, Any]] = []
    class_counts = {name: 0 for name in CLASSIFICATIONS}
    adapter_failures = 0
    for row in rows:
        challenge_id = row["challenge_id"]
        status = row["adapter_status"]
        outcome = row.get("model_outcome")
        classification = row.get("classification")
        score_row = score_details[challenge_id]
        require(score_row.get("adapter_status") == status, f"SOURCE_SCORE_STATUS_MISMATCH:{experiment_id}:{challenge_id}")
        require(score_row.get("semantic_outcome") == outcome, f"SOURCE_SCORE_OUTCOME_MISMATCH:{experiment_id}:{challenge_id}")
        require(score_row.get("classification") == classification, f"SOURCE_SCORE_CLASSIFICATION_MISMATCH:{experiment_id}:{challenge_id}")
        require(row.get("expected_v0_outcome") == oracle_outcomes[challenge_id], f"SOURCE_ORACLE_MISMATCH:{experiment_id}:{challenge_id}")
        if status == "RESPONSE_VALID":
            require(outcome in {"PRESERVED", "VIOLATED", "UNVERIFIABLE"}, f"INVALID_SOURCE_OUTCOME:{experiment_id}:{challenge_id}")
            require(classification in CLASSIFICATIONS, f"INVALID_SOURCE_CLASSIFICATION:{experiment_id}:{challenge_id}")
            class_counts[classification] += 1
        else:
            require(outcome is None and classification is None, f"ADAPTER_FAILURE_HAS_SEMANTIC_RESULT:{experiment_id}:{challenge_id}")
            adapter_failures += 1
        observations.append(
            {
                "challenge_id": challenge_id,
                "protected_relation": row["protected_relation"],
                "evaluator_outcome": outcome,
                "frozen_expected_outcome": oracle_outcomes[challenge_id],
                "mismatch_classification": classification,
                "adapter_status": status,
                "request_sha256": row["request_sha256"],
                "raw_output_sha256": row.get("raw_output_sha256", row.get("raw_response_sha256")),
                "wrapped_response_sha256": row.get(
                    "wrapped_response_sha256", row.get("normalized_response_sha256")
                ),
            }
        )
    derived_aggregates = {
        "valid_semantic_judgments": 6 - adapter_failures,
        "adapter_failures": adapter_failures,
        **class_counts,
    }
    source_aggregates = final.get("aggregates", {})
    require(source_aggregates.get("semantic_responses") == 6 - adapter_failures, f"SOURCE_AGGREGATE_VALID_MISMATCH:{experiment_id}")
    require(source_aggregates.get("adapter_failure_total") == adapter_failures, f"SOURCE_AGGREGATE_FAILURE_MISMATCH:{experiment_id}")
    require(source_aggregates.get("classifications") == class_counts, f"SOURCE_AGGREGATE_CLASSIFICATION_MISMATCH:{experiment_id}")
    return {
        "experiment_id": experiment_id,
        "bundle_path": f"first-runs/{experiment_id}",
        "source_result_path": f"first-runs/{experiment_id}/final-results.json",
        "observations": observations,
        "aggregates": derived_aggregates,
    }


def derive_matrix(evidence_root: Path, repo_root: Path) -> dict[str, Any]:
    oracle_outcomes = _oracle_outcomes(repo_root)
    models = [_derive_model_matrix(evidence_root, experiment_id, oracle_outcomes) for experiment_id in COMPARABLE_EXPERIMENTS]
    repeated: list[dict[str, Any]] = []
    for challenge_id in CHALLENGE_IDS:
        observations = [
            (model["experiment_id"], next(row for row in model["observations"] if row["challenge_id"] == challenge_id))
            for model in models
        ]
        hits = [
            experiment_id
            for experiment_id, row in observations
            if row["mismatch_classification"] == "UNSAFE_FALSE_PRESERVATION"
        ]
        if len(hits) >= 2:
            require(
                {row["frozen_expected_outcome"] for _, row in observations} == {"VIOLATED"},
                f"REPEATED_UNSAFE_FINDING_EXPECTED_CONFLICT:{challenge_id}",
            )
            repeated.append(
                {
                    "challenge_id": challenge_id,
                    "frozen_expected_outcome": "VIOLATED",
                    "classification": "UNSAFE_FALSE_PRESERVATION",
                    "experiments": hits,
                    "observation_count": len(hits),
                    "finding": (
                        f"{challenge_id} produced UNSAFE_FALSE_PRESERVATION in two distinct evaluated "
                        "model families/configurations in these exact first-run observations."
                    ),
                }
            )
    return {
        "schema": "protected-relation-external-evaluator-first-run-matrix.v0",
        "comparable_experiments": list(COMPARABLE_EXPERIMENTS),
        "excluded_experiments": [
            {
                "experiment_id": "qwen2.5-3b-pre-wrapper-repair",
                "reason": "PRE_WRAPPER_REPAIR_PROTOCOL_EVIDENCE_NOT_A_COMPARABLE_SEMANTIC_BASELINE",
            }
        ],
        "models": models,
        "repeated_security_significant_observations": repeated,
        "sampling_boundary": "ONE_FIRST_RUN_SAMPLE_PER_MODEL_AND_CHALLENGE_NO_STABILITY_CLAIM",
    }


def _bundle_stats(entries: dict[str, dict[str, Any]], experiment_id: str) -> dict[str, Any]:
    prefix = f"first-runs/{experiment_id}/"
    selected = [entry for path, entry in entries.items() if path.startswith(prefix)]
    canonical_rows = [
        {
            "path": entry["path"][len(prefix) :],
            "byte_length": entry["byte_length"],
            "sha256": entry["sha256"],
        }
        for entry in selected
    ]
    aggregate = sha256_bytes(
        json.dumps(canonical_rows, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    )
    return {
        "file_count": len(selected),
        "byte_total": sum(entry["byte_length"] for entry in selected),
        "aggregate_inventory_sha256": aggregate,
    }


def validate_record(
    evidence_root: Path,
    inventory: dict[str, Any],
    entries: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    record = load_json(evidence_root / "evidence-record.json")
    require(isinstance(record, dict), "MALFORMED_EVIDENCE_RECORD")
    require(record.get("schema") == "protected-relation-external-evaluator-evidence-record.v0", "WRONG_EVIDENCE_RECORD_SCHEMA")
    require(record.get("version") == "v0", "WRONG_EVIDENCE_RECORD_VERSION")
    require(record.get("benchmark") == "Protected Relation Fixtures", "WRONG_BENCHMARK_IDENTITY")
    authority = record.get("authority", {})
    require(authority.get("frozen_v0_commit") == V0_COMMIT, "WRONG_FROZEN_V0_COMMIT")
    require(authority.get("frozen_v0_tree") == V0_TREE, "WRONG_FROZEN_V0_TREE")
    require(authority.get("external_adapter_commit") == ADAPTER_COMMIT, "WRONG_ADAPTER_COMMIT_IDENTITY")
    require(
        authority.get("evaluator_output_schema_sha256") == EVALUATOR_OUTPUT_SCHEMA_SHA256,
        "WRONG_EVALUATOR_OUTPUT_SCHEMA_DIGEST",
    )
    require(authority.get("response_schema_sha256") == RESPONSE_SCHEMA_SHA256, "WRONG_RESPONSE_SCHEMA_DIGEST")
    payload = record.get("payload_inventory", {})
    require(payload.get("path") == "payload-inventory.json", "WRONG_PAYLOAD_INVENTORY_PATH")
    require(
        payload.get("sha256") == sha256_path(evidence_root / "payload-inventory.json"),
        "WRONG_PAYLOAD_INVENTORY_DIGEST",
    )
    require(payload.get("total_files") == inventory["total_files"], "RECORD_PAYLOAD_FILE_TOTAL_MISMATCH")
    require(payload.get("total_bytes") == inventory["total_bytes"], "RECORD_PAYLOAD_BYTE_TOTAL_MISMATCH")
    matrix = record.get("first_run_matrix", {})
    require(matrix.get("path") == "first-run-matrix.json", "WRONG_MATRIX_PATH")
    require(matrix.get("sha256") == sha256_path(evidence_root / "first-run-matrix.json"), "WRONG_MATRIX_DIGEST")
    experiments = record.get("experiments")
    require(isinstance(experiments, list), "MALFORMED_EXPERIMENT_RECORDS")
    require([row.get("experiment_id") for row in experiments] == list(ALL_EXPERIMENTS), "EXPERIMENT_RECORD_ORDER_OR_MEMBERSHIP_MISMATCH")
    for row in experiments:
        experiment_id = row["experiment_id"]
        spec = EXPERIMENT_SPECS[experiment_id]
        bundle_root = evidence_root / "first-runs" / experiment_id
        capture = _validate_capture(bundle_root, experiment_id)
        require(row.get("path") == f"first-runs/{experiment_id}", f"WRONG_EXPERIMENT_PATH:{experiment_id}")
        require(row.get("phase") == spec["phase"], f"WRONG_EXPERIMENT_PHASE:{experiment_id}")
        require(row.get("comparable_semantic_baseline") is spec["comparable"], f"WRONG_COMPARABILITY:{experiment_id}")
        identity = row.get("model_identity", {})
        for field in ("provider", "model", "model_id", "model_blob_digest"):
            require(identity.get(field) == spec[field], f"EVIDENCE_RECORD_MODEL_IDENTITY_MISMATCH:{experiment_id}:{field}")
            require(identity.get(field) == capture["config"][field], f"CAPTURE_RECORD_MODEL_IDENTITY_MISMATCH:{experiment_id}:{field}")
        require(identity.get("runtime") == "Ollama" and identity.get("runtime_version") == "0.15.2", f"EVIDENCE_RECORD_RUNTIME_MISMATCH:{experiment_id}")
        capture_evidence = row.get("capture_evidence", {})
        expected_capture = {
            "model_calls": 6,
            "one_call_per_challenge": True,
            "no_retries": spec["no_retries"],
            "no_conversation_memory": True,
            "oracle_leakage": "PASS",
            "capture_before_scoring": spec["capture_before_scoring"],
        }
        require(capture_evidence == expected_capture, f"EVIDENCE_RECORD_CAPTURE_MISMATCH:{experiment_id}")
        require(row.get("payload") == _bundle_stats(entries, experiment_id), f"EVIDENCE_RECORD_PAYLOAD_MISMATCH:{experiment_id}")
    boundary = record.get("authority_boundary", {})
    require(
        boundary.get("reproduction_claim")
        == "Committed transcripts bind what was observed under the recorded evaluator identity and configuration; they do not prove that a nondeterministic evaluator will reproduce the same judgment.",
        "AUTHORITY_BOUNDARY_REPRODUCTION_DRIFT",
    )
    require(
        boundary.get("oracle_claim")
        == "The frozen v0 oracle is benchmark authority for these comparisons, not a claim of universal external-domain truth.",
        "AUTHORITY_BOUNDARY_ORACLE_DRIFT",
    )
    require(
        boundary.get("sampling_claim")
        == "Each comparable result is one first-run sample per model and challenge, with no retry and no stability or statistical-significance claim.",
        "AUTHORITY_BOUNDARY_SAMPLING_DRIFT",
    )
    return record


def validate_git_identities(repo_root: Path) -> None:
    def git(*args: str) -> bytes:
        result = subprocess.run(["git", *args], cwd=repo_root, capture_output=True, check=False)
        require(result.returncode == 0, f"GIT_IDENTITY_CHECK_FAILED:{' '.join(args)}")
        return result.stdout

    require(git("rev-parse", "v0^{commit}").decode().strip() == V0_COMMIT, "V0_TAG_COMMIT_MISMATCH")
    require(git("rev-parse", "v0^{tree}").decode().strip() == V0_TREE, "V0_TAG_TREE_MISMATCH")
    result = subprocess.run(
        ["git", "merge-base", "--is-ancestor", ADAPTER_COMMIT, "HEAD"],
        cwd=repo_root,
        capture_output=True,
        check=False,
    )
    require(result.returncode == 0, "ADAPTER_COMMIT_NOT_IN_HEAD_ANCESTRY")
    schemas = {
        "adapters/v0/evaluator-output-schema.json": EVALUATOR_OUTPUT_SCHEMA_SHA256,
        "adapters/v0/response-schema.json": RESPONSE_SCHEMA_SHA256,
    }
    for path, expected in schemas.items():
        require(sha256_path(repo_root / path) == expected, f"CURRENT_SCHEMA_DIGEST_MISMATCH:{path}")
        require(sha256_bytes(git("show", f"{ADAPTER_COMMIT}:{path}")) == expected, f"ADAPTER_COMMIT_SCHEMA_DIGEST_MISMATCH:{path}")


def validate_evidence(
    evidence_root: Path = EVIDENCE_ROOT,
    *,
    repo_root: Path = ROOT,
    check_git: bool = True,
) -> dict[str, Any]:
    inventory, entries = validate_payload_inventory(evidence_root)
    record = validate_record(evidence_root, inventory, entries)
    matrix = load_json(evidence_root / "first-run-matrix.json")
    require(matrix == derive_matrix(evidence_root, repo_root), "FIRST_RUN_MATRIX_SOURCE_MISMATCH")
    require(
        [row["challenge_id"] for row in matrix["repeated_security_significant_observations"]] == ["prf-005"],
        "REPEATED_UNSAFE_FINDING_MISMATCH",
    )
    if check_git:
        validate_git_identities(repo_root)
    return {"inventory": inventory, "record": record, "matrix": matrix}


def main() -> int:
    try:
        result = validate_evidence()
    except (EvidenceValidationError, OSError, KeyError, TypeError) as exc:
        print(f"external evaluator evidence validation: FAIL: {exc}")
        return 1
    inventory = result["inventory"]
    matrix = result["matrix"]
    print(
        "external evaluator evidence validation: PASS "
        f"({inventory['total_files']} payload files; {inventory['total_bytes']} bytes; "
        f"{len(matrix['models'])} comparable first-run experiments; repeated unsafe case: prf-005)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
