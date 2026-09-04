from __future__ import annotations

from collections import Counter
import hashlib
import json
from pathlib import Path, PurePosixPath
import subprocess
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from adapters.v0.score_results import CLASSIFICATION_NAMES, score_results  # noqa: E402


EVIDENCE_ROOT = ROOT / "evidence/external-evaluators/v0/repeated-runs"
PAYLOAD_ROOT = EVIDENCE_ROOT / "payload"
V0_COMMIT = "98ccba804c725777e155ad2f1a07bae49754376b"
V0_TREE = "c2449cb3a52e60c4f93e3c8a3a35c086c47f2d63"
ADAPTER_COMMIT = "cf39a37d66222522368e719e3910c27a3eab31dd"
FIRST_RUN_MAIN = "5fdd96a0ca9df399bb946fdba089992b8b3ad4db"
EVALUATOR_SCHEMA_SHA256 = "60c3c89bf2ae7d5d406c4449da5e3de728cd37c9ab3749038b7da30193a33fff"
RESPONSE_SCHEMA_SHA256 = "a8557965c090cb8e6d1a4dbc0e2b7cd44832e1b16dd2021d63a92729aaab0a7a"
MODELS = ("qwen2.5-3b-instruct", "qwen2.5-coder-7b", "llama3.1-8b")
CHALLENGES = tuple(f"prf-{index:03d}" for index in range(1, 7))
OUTCOMES = ("PRESERVED", "VIOLATED", "UNVERIFIABLE")
UNSAFE = ("UNSAFE_FALSE_PRESERVATION", "UNSAFE_UNVERIFIABLE_UPGRADE")
FIRST_RUN_IDS = {
    "qwen2.5-3b-instruct": "qwen2.5-3b-post-wrapper-repair",
    "qwen2.5-coder-7b": "qwen2.5-coder-7b",
    "llama3.1-8b": "llama3.1-8b",
}
EXPECTED_MODELS = {
    "qwen2.5-3b-instruct": ("qwen2.5:3b-instruct", "357c53fb659c", "5ee4f07cdb9beadbbb293e85803c569b01bd37ed059d2715faa7bb405f31caa6"),
    "qwen2.5-coder-7b": ("qwen2.5-coder:7b", "dae161e27b0e", "60e05f2100071479f596b964f89f510f057ce397ea22f2833a0cfe029bfc2463"),
    "llama3.1-8b": ("llama3.1:8b", "46e0c10c039e", "667b0c1932bc6ffc593ed1d03f895bf2dc8dc6df21db3042284a6f4416b06a29"),
}


class RepeatedEvidenceError(ValueError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RepeatedEvidenceError(message)


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def sha256_path(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def _duplicate_guard(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, item in pairs:
        require(key not in value, f"DUPLICATE_JSON_KEY:{key}")
        value[key] = item
    return value


def load_json(path: Path, *, strict_framing: bool = True) -> Any:
    require(path.is_file(), f"MISSING_FILE:{path}")
    raw = path.read_bytes()
    if strict_framing:
        require(raw and not raw.startswith(b"\xef\xbb\xbf") and b"\r" not in raw and raw.endswith(b"\n"), f"INVALID_JSON_FRAMING:{path}")
    try:
        return json.loads(raw.decode("utf-8"), object_pairs_hook=_duplicate_guard)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RepeatedEvidenceError(f"MALFORMED_JSON:{path}:{exc}") from exc


def rate(numerator: int, denominator: int) -> dict[str, Any]:
    return {"numerator": numerator, "denominator": denominator, "decimal": round(numerator / denominator, 12) if denominator else None}


def validate_payload_inventory(root: Path) -> dict[str, Any]:
    inventory = load_json(root / "payload-inventory.json")
    require(set(inventory) == {"schema", "entries", "total_files", "total_bytes"}, "INVALID_INVENTORY_FIELDS")
    require(inventory["schema"] == "prf-external-evaluator-repeated-payload-inventory.v0", "INVALID_INVENTORY_SCHEMA")
    entries = inventory["entries"]
    require(isinstance(entries, list), "INVALID_INVENTORY_ENTRIES")
    paths: list[str] = []
    for entry in entries:
        require(isinstance(entry, dict) and set(entry) == {"path", "byte_length", "sha256"}, "INVALID_INVENTORY_ENTRY")
        path = entry["path"]
        require(isinstance(path, str) and path.startswith("payload/") and "\\" not in path, "INVALID_INVENTORY_PATH")
        pure = PurePosixPath(path)
        require(not pure.is_absolute() and ".." not in pure.parts, "UNSAFE_INVENTORY_PATH")
        require(path not in paths, f"DUPLICATE_INVENTORY_PATH:{path}")
        require(isinstance(entry["byte_length"], int) and entry["byte_length"] >= 0, f"INVALID_BYTE_LENGTH:{path}")
        require(isinstance(entry["sha256"], str) and len(entry["sha256"]) == 64, f"INVALID_SHA256:{path}")
        paths.append(path)
        payload_path = root / path
        require(payload_path.is_file(), f"MISSING_PAYLOAD:{path}")
        raw = payload_path.read_bytes()
        require(len(raw) == entry["byte_length"], f"PAYLOAD_LENGTH_MISMATCH:{path}")
        require(sha256_bytes(raw) == entry["sha256"], f"PAYLOAD_SHA256_MISMATCH:{path}")
    require(paths == sorted(paths), "NON_CANONICAL_INVENTORY_ORDER")
    actual = sorted(f"payload/{path.relative_to(root / 'payload').as_posix()}" for path in (root / "payload").rglob("*") if path.is_file())
    require(paths == actual, "PAYLOAD_CLOSED_UNIVERSE_MISMATCH")
    require(inventory["total_files"] == len(entries), "PAYLOAD_FILE_TOTAL_MISMATCH")
    require(inventory["total_bytes"] == sum(row["byte_length"] for row in entries), "PAYLOAD_BYTE_TOTAL_MISMATCH")
    return inventory


def validate_capture_closure(root: Path) -> dict[str, Any]:
    payload = root / "payload"
    inventory = load_json(payload / "capture-inventory.json")
    require(inventory.get("schema") == "prf-repeated-capture-inventory.v0", "WRONG_CAPTURE_INVENTORY_SCHEMA")
    entries = inventory.get("entries")
    require(isinstance(entries, list), "MALFORMED_CAPTURE_INVENTORY")
    paths = [row.get("path") for row in entries]
    require(paths == sorted(paths) and len(paths) == len(set(paths)), "CAPTURE_INVENTORY_ORDER_OR_DUPLICATE")
    for row in entries:
        raw = (payload / row["path"]).read_bytes()
        require(len(raw) == row["byte_length"] and sha256_bytes(raw) == row["sha256"], f"CAPTURE_DRIFT:{row['path']}")
    require(inventory.get("total_files") == len(entries), "CAPTURE_FILE_TOTAL_MISMATCH")
    require(inventory.get("total_bytes") == sum(row["byte_length"] for row in entries), "CAPTURE_BYTE_TOTAL_MISMATCH")
    summary = load_json(payload / "capture-summary.json")
    require(summary.get("capture_closed") is True and summary.get("scoring_performed") is False, "CAPTURE_ORDER_BOUNDARY_MISSING")
    require(summary.get("scheduled_observations") == 180 and summary.get("attempted_observations") == 180 and summary.get("captured_observations") == 180, "CAPTURE_TOTAL_MISMATCH")
    reference = summary.get("capture_inventory", {})
    require(reference.get("sha256") == sha256_path(payload / "capture-inventory.json"), "CAPTURE_INVENTORY_DIGEST_MISMATCH")
    require(reference.get("total_files") == inventory["total_files"] and reference.get("total_bytes") == inventory["total_bytes"], "CAPTURE_INVENTORY_REFERENCE_MISMATCH")
    leakage = load_json(payload / "metadata/oracle-leakage-check.json")
    require(leakage.get("status") == "PASS" and leakage.get("templates_checked") == 18 and leakage.get("answer_bearing_markers_found") == 0, "ORACLE_LEAKAGE_BOUNDARY_FAILURE")
    return summary


def _historical_map(repo_root: Path) -> dict[str, dict[str, dict[str, Any]]]:
    first = load_json(repo_root / "evidence/external-evaluators/v0/first-run-matrix.json")
    require("qwen2.5-3b-pre-wrapper-repair" not in first["comparable_experiments"], "PRE_REPAIR_BASELINE_INCLUDED")
    experiments = {row["experiment_id"]: row for row in first["models"]}
    return {model: {row["challenge_id"]: row for row in experiments[experiment]["observations"]} for model, experiment in FIRST_RUN_IDS.items()}


def derive(root: Path, repo_root: Path) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    payload = root / "payload"
    oracle = load_json(repo_root / "corpus/v0/oracle/expected-results.json")
    expected = {key: row["semantic_outcome"] for key, row in oracle["results"].items()}
    historical = _historical_map(repo_root)
    identity_rows = load_json(payload / "metadata/model-identities.json")["models"]
    identities = {row["model_key"]: row for row in identity_rows}
    require(tuple(identities) == MODELS, "MODEL_IDENTITY_ORDER_OR_COVERAGE_MISMATCH")
    for model, expected_identity in EXPECTED_MODELS.items():
        row = identities[model]
        require((row["model"], row["model_id"], row["payload_sha256"]) == expected_identity, f"MODEL_IDENTITY_MISMATCH:{model}")
        require(row["available"] is True and row["runtime_version"] == "0.15.2", f"MODEL_RUNTIME_MISMATCH:{model}")

    models = []
    stability_models = []
    all_rows = []
    for model in MODELS:
        challenge_records = []
        stability_records = []
        aggregate_classes = Counter()
        aggregate_statuses = Counter()
        for challenge in CHALLENGES:
            rows = []
            outcomes = Counter()
            classes = Counter()
            statuses = Counter()
            for run_index in range(1, 11):
                base = payload / model / challenge / f"run-{run_index:02d}"
                observation = load_json(base / "observation.json")
                require(observation["model_key"] == model and observation["challenge_id"] == challenge and observation["run_index"] == run_index, "OBSERVATION_IDENTITY_MISMATCH")
                require(observation.get("semantic_retries") == 0, "SEMANTIC_RETRY_DETECTED")
                request_raw = (base / "request.json").read_bytes()
                stdout = (base / "stdout.bin").read_bytes()
                stderr = (base / "stderr.bin").read_bytes()
                require(sha256_bytes(request_raw) == observation["request_bytes_sha256"], "REQUEST_DIGEST_MISMATCH")
                require(sha256_bytes(stdout) == observation["stdout_sha256"], "STDOUT_DIGEST_MISMATCH")
                require(sha256_bytes(stderr) == observation["stderr_sha256"], "STDERR_DIGEST_MISMATCH")
                request = json.loads(request_raw.decode("utf-8"), object_pairs_hook=_duplicate_guard)
                transcript = load_json(base / "transcript.json")
                score = score_results([request], [transcript])
                detail = score["details"][0]
                status = detail["adapter_status"]
                outcome = detail.get("semantic_outcome")
                classification = detail.get("classification")
                require(status == observation["adapter_status"] and outcome == observation["semantic_outcome"], "OBSERVATION_TRANSCRIPT_MISMATCH")
                if status == "RESPONSE_VALID":
                    require(outcome in OUTCOMES and classification in CLASSIFICATION_NAMES, "VALID_RESPONSE_WITHOUT_SEMANTICS")
                    evaluator_output = load_json(base / "evaluator-output.json")
                    wrapped = load_json(base / "wrapped-response.json")
                    require(sha256_bytes(json.dumps(evaluator_output, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode()) == observation["evaluator_output_digest"], "EVALUATOR_OUTPUT_DIGEST_MISMATCH")
                    require(sha256_bytes(json.dumps(wrapped, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode()) == observation["wrapped_response_digest"], "WRAPPED_RESPONSE_DIGEST_MISMATCH")
                    outcomes[outcome] += 1
                    classes[classification] += 1
                    aggregate_classes[classification] += 1
                else:
                    require(outcome is None and classification is None and observation["wrapped_response_digest"] is None, "ADAPTER_FAILURE_UPGRADED_TO_SEMANTICS")
                statuses[status] += 1
                aggregate_statuses[status] += 1
                row = {"model_key": model, "challenge_id": challenge, "protected_relation": request["protected_relation_profile"]["kind"], "run_index": run_index, "scheduled_observations": 1, "adapter_status": status, "semantic_outcome": outcome, "frozen_expected_outcome": expected[challenge], "benchmark_classification": classification, "request_bytes_sha256": observation["request_bytes_sha256"], "stdout_sha256": observation["stdout_sha256"], "stderr_sha256": observation["stderr_sha256"], "evaluator_output_digest": observation["evaluator_output_digest"], "wrapped_response_digest": observation["wrapped_response_digest"], "invocation_context_digest": observation["invocation_context_digest"]}
                require(load_json(payload / "scoring" / model / challenge / f"run-{run_index:02d}.json") == row, "SCORING_ROW_DERIVATION_MISMATCH")
                rows.append(row)
                all_rows.append(row)
            valid = sum(outcomes.values())
            modal_count = max(outcomes.values()) if valid else 0
            modal = sorted(key for key, value in outcomes.items() if value == modal_count) if valid else []
            pair_total = valid * (valid - 1) // 2
            disagree = pair_total - sum(value * (value - 1) // 2 for value in outcomes.values())
            old = historical[model][challenge]
            if old["adapter_status"] != "RESPONSE_VALID": recurrence = "HISTORICAL_ADAPTER_FAILURE"
            elif outcomes[old["evaluator_outcome"]] == 0: recurrence = "DID_NOT_RECUR"
            elif old["evaluator_outcome"] in modal: recurrence = "RECURRED_MODAL"
            else: recurrence = "RECURRED_NONMODAL"
            unsafe_count = sum(classes[name] for name in UNSAFE)
            record = {"challenge_id": challenge, "protected_relation": rows[0]["protected_relation"], "frozen_expected_outcome": expected[challenge], "scheduled_observations": 10, "valid_semantic_observations": valid, "adapter_failures": 10 - valid, "adapter_status_counts": dict(sorted(statuses.items())), "outcome_counts": {name: outcomes[name] for name in OUTCOMES}, "classification_counts": {name: classes[name] for name in CLASSIFICATION_NAMES}, "classification_rates_scheduled": {name: rate(classes[name], 10) for name in CLASSIFICATION_NAMES}, "classification_rates_valid": {name: rate(classes[name], valid) for name in CLASSIFICATION_NAMES}, "unsafe_observed_rate": rate(unsafe_count, 10), "conditional_valid_unsafe_rate": rate(unsafe_count, valid), "modal_outcomes": modal, "modal_outcome_share": rate(modal_count, valid) if valid else "NOT_COMPUTABLE", "nonmodal_valid_judgment_rate": rate(valid - modal_count, valid) if valid else "NOT_COMPUTABLE", "pairwise_semantic_disagreement_rate": rate(disagree, pair_total) if pair_total else "NOT_COMPUTABLE", "historical_first_run": {"experiment_id": FIRST_RUN_IDS[model], "adapter_status": old["adapter_status"], "semantic_outcome": old["evaluator_outcome"], "benchmark_classification": old["mismatch_classification"], "fresh_distribution_recurrence": recurrence, "counted_in_fresh_denominator": False}, "observations": rows}
            challenge_records.append(record)
            stability_records.append({key: record[key] for key in ("challenge_id", "protected_relation", "valid_semantic_observations", "adapter_failures", "outcome_counts", "modal_outcomes", "modal_outcome_share", "nonmodal_valid_judgment_rate", "pairwise_semantic_disagreement_rate", "historical_first_run")})
        valid_model = sum(row["adapter_status"] == "RESPONSE_VALID" for row in all_rows if row["model_key"] == model)
        models.append({"model_key": model, "scheduled_observations": 60, "attempted_observations": 60, "captured_observations": 60, "valid_semantic_observations": valid_model, "adapter_failures": 60 - valid_model, "adapter_status_counts": dict(sorted(aggregate_statuses.items())), "classification_counts": {name: aggregate_classes[name] for name in CLASSIFICATION_NAMES}, "challenges": challenge_records})
        stability_models.append({"model_key": model, "challenges": stability_records})
    total_classes = Counter(row["benchmark_classification"] for row in all_rows if row["benchmark_classification"] is not None)
    total_status = Counter(row["adapter_status"] for row in all_rows)
    matrix = {"schema": "prf-external-evaluator-repeated-run-matrix.v0", "fresh_observation_policy": {"scheduled": 180, "one_call_per_observation": True, "semantic_retries": 0, "historical_first_runs_counted_in_denominator": False, "pre_wrapper_repair_used_as_comparable_baseline": False}, "overall": {"scheduled_observations": 180, "attempted_observations": 180, "captured_observations": 180, "valid_semantic_observations": sum(total_classes.values()), "adapter_failures": 180 - sum(total_classes.values()), "adapter_status_counts": dict(sorted(total_status.items())), "classification_counts": {name: total_classes[name] for name in CLASSIFICATION_NAMES}, "security_significant_failures": sum(total_classes[name] for name in UNSAFE)}, "models": models}
    stability = {"schema": "prf-external-evaluator-semantic-stability-summary.v0", "denominator_rule": "valid semantic judgments only; adapter failures excluded", "frequency_interpretation": "empirical observed frequencies, not calibrated probabilities", "models": stability_models}
    repeated = []
    cross_rows = []
    for challenge in CHALLENGES:
        records = {model["model_key"]: next(row for row in model["challenges"] if row["challenge_id"] == challenge) for model in models}
        false_models = [model for model, row in records.items() if row["classification_counts"]["UNSAFE_FALSE_PRESERVATION"]]
        upgrade_models = [model for model, row in records.items() if row["classification_counts"]["UNSAFE_UNVERIFIABLE_UPGRADE"]]
        for name, selected in (("UNSAFE_FALSE_PRESERVATION", false_models), ("UNSAFE_UNVERIFIABLE_UPGRADE", upgrade_models)):
            if len(selected) >= 2:
                repeated.append({"challenge_id": challenge, "protected_relation": next(iter(records.values()))["protected_relation"], "classification": name, "models": selected, "counts_by_model": {model: records[model]["classification_counts"][name] for model in selected}})
        sets = {model: {name for name, count in row["outcome_counts"].items() if count} for model, row in records.items()}
        union = set().union(*sets.values())
        cross_rows.append({"challenge_id": challenge, "protected_relation": next(iter(records.values()))["protected_relation"], "outcomes_observed_by_model": {model: sorted(values) for model, values in sets.items()}, "models_disagree_semantically": len(union) > 1, "all_evaluated_models_agree_on_one_outcome": len(union) == 1 and all(len(values) == 1 for values in sets.values()), "all_evaluated_models_match_all_valid_observations": all(row["adapter_failures"] == 0 and row["classification_counts"]["MATCH"] == 10 for row in records.values()), "all_evaluated_models_have_no_match": all(row["valid_semantic_observations"] > 0 and row["classification_counts"]["MATCH"] == 0 for row in records.values()), "unsafe_false_preservation_models": false_models, "unsafe_unverifiable_upgrade_models": upgrade_models})
    cross = {"schema": "prf-external-evaluator-cross-model-repeated-summary.v0", "minimum_models_for_repeated_cross_model_finding": 2, "repeated_security_significant_findings": repeated, "challenges": cross_rows, "claim_boundary": "These are benchmark-relative findings from exact recorded invocations; they are not universal, deterministic, statistically significant by themselves, or external-domain truth."}
    return matrix, stability, cross


def validate_record_and_report(root: Path, inventory: dict[str, Any], matrix: dict[str, Any], stability: dict[str, Any], cross: dict[str, Any]) -> None:
    record = load_json(root / "evidence-record.json")
    require(record.get("schema") == "prf-external-evaluator-repeated-evidence-record.v0", "WRONG_RECORD_SCHEMA")
    authority = record.get("authority", {})
    require(authority == {"frozen_v0_commit": V0_COMMIT, "frozen_v0_tree": V0_TREE, "external_adapter_commit": ADAPTER_COMMIT, "first_run_evidence_canonical_main": FIRST_RUN_MAIN, "evaluator_output_schema_sha256": EVALUATOR_SCHEMA_SHA256, "response_schema_sha256": RESPONSE_SCHEMA_SHA256}, "WRONG_AUTHORITY_IDENTITY")
    policy = record.get("methodology", {})
    require(policy.get("scheduled_fresh_observations") == 180 and policy.get("runs_per_model_challenge") == 10 and policy.get("semantic_retries") == 0 and policy.get("capture_before_scoring") is True, "WRONG_METHOD_POLICY")
    require(policy.get("historical_first_runs_counted_in_fresh_denominator") is False and policy.get("pre_wrapper_repair_comparable") is False, "HISTORICAL_DENOMINATOR_CONTAMINATION")
    inv = record.get("payload_inventory", {})
    require(inv == {"path": "payload-inventory.json", "sha256": sha256_path(root / "payload-inventory.json"), "total_files": inventory["total_files"], "total_bytes": inventory["total_bytes"]}, "RECORD_INVENTORY_MISMATCH")
    require(record.get("capture_summary") == {"path": "payload/capture-summary.json", "sha256": sha256_path(root / "payload/capture-summary.json")}, "RECORD_CAPTURE_MISMATCH")
    require(record.get("secret_scan") == {"status": "PASS", "actual_credentials_detected": 0, "detector_source_literal_matches": 1, "detector_source_literal_path": "payload/harness/prepare_capture.py"}, "SECRET_SCAN_RECORD_MISMATCH")
    for name, value in (("repeated-run-matrix.json", matrix), ("stability-summary.json", stability), ("cross-model-summary.json", cross)):
        require(load_json(root / name) == value, f"DERIVED_SUMMARY_MISMATCH:{name}")
        require(record["derived_summaries"][name] == {"path": name, "sha256": sha256_path(root / name)}, f"RECORD_SUMMARY_DIGEST_MISMATCH:{name}")
    report = (root / "REPORT.md").read_text(encoding="utf-8")
    require("\r" not in report and report.startswith("# PRF External Evaluator Repeated-Run Study — v0\n"), "REPORT_FRAMING_OR_TITLE_MISMATCH")
    overall = matrix["overall"]
    required_claims = [
        f"{overall['scheduled_observations']} scheduled fresh oracle-blind observations",
        f"{overall['valid_semantic_observations']} valid semantic judgments",
        f"{overall['adapter_failures']} adapter failures",
        f"{overall['security_significant_failures']} security-significant benchmark-relative mismatches",
        f"- Payload files: {inventory['total_files']}", f"- Payload bytes: {inventory['total_bytes']}",
        f"- Payload inventory SHA-256: `{sha256_path(root / 'payload-inventory.json')}`",
    ]
    for model in matrix["models"]:
        counts = model["classification_counts"]
        required_claims.append(f"| {model['valid_semantic_observations']}/60 | {model['adapter_failures']} | {counts['MATCH']} | {counts['UNSAFE_FALSE_PRESERVATION']} | {counts['UNSAFE_UNVERIFIABLE_UPGRADE']} |")
        for row in model["challenges"]:
            out = row["outcome_counts"]
            required_claims.append(f"| {out['PRESERVED']} / {out['VIOLATED']} / {out['UNVERIFIABLE']} |")
    for claim in required_claims:
        require(claim in report, f"REPORT_CLAIM_MISMATCH:{claim}")
    boundary = "These results characterize the recorded repeated blind observations under the frozen PRF v0 benchmark and recorded evaluator configurations. They do not establish universal model behavior, deterministic semantic outcomes, statistical significance by themselves, or external-domain truth beyond the benchmark authority."
    require(boundary in report and record.get("authority_boundary") == boundary, "AUTHORITY_BOUNDARY_DRIFT")


def validate_git(repo_root: Path) -> None:
    def git(*args: str) -> str:
        result = subprocess.run(["git", *args], cwd=repo_root, capture_output=True, text=True, check=False)
        require(result.returncode == 0, f"GIT_COMMAND_FAILED:{' '.join(args)}")
        return result.stdout.strip()
    require(git("rev-parse", "v0^{commit}") == V0_COMMIT and git("rev-parse", "v0^{tree}") == V0_TREE, "FROZEN_V0_TAG_DRIFT")
    require(subprocess.run(["git", "merge-base", "--is-ancestor", ADAPTER_COMMIT, "HEAD"], cwd=repo_root).returncode == 0, "ADAPTER_NOT_IN_ANCESTRY")
    require(sha256_path(repo_root / "adapters/v0/evaluator-output-schema.json") == EVALUATOR_SCHEMA_SHA256, "EVALUATOR_SCHEMA_DRIFT")
    require(sha256_path(repo_root / "adapters/v0/response-schema.json") == RESPONSE_SCHEMA_SHA256, "RESPONSE_SCHEMA_DRIFT")
    protected = ["evidence/external-evaluators/v0/first-runs", "evidence/external-evaluators/v0/README.md", "evidence/external-evaluators/v0/evidence-record.json", "evidence/external-evaluators/v0/first-run-matrix.json", "evidence/external-evaluators/v0/payload-inventory.json"]
    result = subprocess.run(["git", "diff", "--quiet", FIRST_RUN_MAIN, "--", *protected], cwd=repo_root)
    require(result.returncode == 0, "EXISTING_FIRST_RUN_EVIDENCE_DRIFT")


def validate_repeated_evidence(evidence_root: Path = EVIDENCE_ROOT, *, repo_root: Path = ROOT, check_git: bool = True) -> dict[str, Any]:
    inventory = validate_payload_inventory(evidence_root)
    capture = validate_capture_closure(evidence_root)
    matrix, stability, cross = derive(evidence_root, repo_root)
    validate_record_and_report(evidence_root, inventory, matrix, stability, cross)
    if check_git:
        validate_git(repo_root)
    return {"inventory": inventory, "capture": capture, "matrix": matrix, "stability": stability, "cross": cross}


def main() -> int:
    try:
        result = validate_repeated_evidence()
    except (RepeatedEvidenceError, OSError, KeyError, TypeError, ValueError) as exc:
        print(f"external evaluator repeated evidence validation: FAIL: {exc}")
        return 1
    overall = result["matrix"]["overall"]
    print(f"external evaluator repeated evidence validation: PASS ({overall['captured_observations']}/180 captured; {overall['valid_semantic_observations']} semantic; {overall['adapter_failures']} adapter failures; {result['inventory']['total_files']} payload files)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
