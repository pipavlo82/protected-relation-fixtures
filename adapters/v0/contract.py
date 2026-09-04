from __future__ import annotations

from datetime import datetime, timezone
import base64
import hashlib
import json
from pathlib import Path
import re
import subprocess
from typing import Any

from jsonschema import Draft202012Validator


ROOT = Path(__file__).resolve().parents[2]
REQUEST_SCHEMA_PATH = Path(__file__).with_name("request-schema.json")
EVALUATOR_OUTPUT_SCHEMA_PATH = Path(__file__).with_name("evaluator-output-schema.json")
RESPONSE_SCHEMA_PATH = Path(__file__).with_name("response-schema.json")
CHALLENGE_ROOT = ROOT / "corpus" / "v0" / "challenge" / "cases"
V0_INVENTORY_PATH = ROOT / "releases" / "v0" / "sha256-inventory.json"
V0_INVENTORY_SHA256 = "d29597ea7005c9aac31cfd50cca915d84cb0b203a18564fe654217d7733ded55"

OUTCOMES = {"PRESERVED", "VIOLATED", "UNVERIFIABLE"}
MISMATCH_CLASSIFICATIONS = {
    "MATCH",
    "UNSAFE_FALSE_PRESERVATION",
    "UNSAFE_UNVERIFIABLE_UPGRADE",
    "FALSE_VIOLATION",
    "PRESERVATION_NOT_ESTABLISHED",
    "VIOLATION_NOT_ESTABLISHED",
    "UNVERIFIABLE_MISCLASSIFIED_AS_VIOLATION",
}
SUPPORTED_CHALLENGE_IDS = {f"prf-{index:03d}" for index in range(1, 7)}
ADAPTER_STATUSES = {
    "RESPONSE_VALID",
    "PROCESS_ERROR",
    "TIMEOUT",
    "EMPTY_RESPONSE",
    "MALFORMED_RESPONSE",
    "INVALID_EVALUATOR_OUTPUT",
}
BANNED_REQUEST_KEYS = {
    "class",
    "expected",
    "expected_outcome",
    "fail_closed_required",
    "metadata",
    "mismatch_classification",
    "oracle",
    "oracle_result",
    "projection_preserved",
    "protected_relation_preserved",
    "semantic_outcome",
    "benchmark_pass",
    "benchmark_result",
}
BANNED_CHALLENGE_EXTRA_KEYS = {"expected", "metadata", "projections", "oracle"}


class AdapterContractViolation(ValueError):
    """A fail-closed adapter-contract violation."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AdapterContractViolation(message)


def canonical_json_bytes(value: Any) -> bytes:
    try:
        text = json.dumps(
            value,
            ensure_ascii=False,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        )
    except (TypeError, ValueError, UnicodeError) as exc:
        raise AdapterContractViolation(f"value is outside canonical JSON domain: {exc}") from exc
    return text.encode("utf-8")


def digest_value(value: Any) -> str:
    return hashlib.sha256(canonical_json_bytes(value)).hexdigest()


def digest_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _load_schema(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _validate_schema(value: Any, schema_path: Path, label: str) -> None:
    errors = sorted(
        Draft202012Validator(_load_schema(schema_path)).iter_errors(value),
        key=lambda error: list(error.absolute_path),
    )
    if errors:
        error = errors[0]
        location = "/".join(str(part) for part in error.absolute_path) or "<root>"
        raise AdapterContractViolation(f"{label} schema violation at {location}: {error.message}")


def _walk(value: Any, path: str = "$") -> list[tuple[str, str | None, Any]]:
    found: list[tuple[str, str | None, Any]] = []
    if isinstance(value, dict):
        for key, child in value.items():
            child_path = f"{path}.{key}"
            found.append((child_path, key, child))
            found.extend(_walk(child, child_path))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            found.extend(_walk(child, f"{path}[{index}]"))
    return found


def assert_oracle_blind_request(request: dict[str, Any]) -> None:
    for path, key, value in _walk(request):
        if key is not None:
            normalized = key.lower().replace("-", "_")
            require(normalized not in BANNED_REQUEST_KEYS, f"ORACLE_LEAKAGE_FIELD:{path}")
        semantic_payload = path.startswith("$.evaluation_input.") or path.startswith(
            "$.protected_relation_profile."
        )
        if isinstance(value, str) and not semantic_payload:
            require(value.upper() not in OUTCOMES, f"ORACLE_LEAKAGE_OUTCOME:{path}")
            require(
                value.upper() not in MISMATCH_CLASSIFICATIONS,
                f"ORACLE_LEAKAGE_CLASSIFICATION:{path}",
            )
            lower = value.lower()
            require("oracle" not in lower and "expected outcome" not in lower, f"ORACLE_LEAKAGE_VALUE:{path}")
    challenge_id = request.get("challenge_id", "")
    require(
        re.fullmatch(r"prf-[0-9]{3}", challenge_id) is not None,
        "CHALLENGE_ID_NOT_OPAQUE",
    )


def validate_request(request: Any) -> dict[str, Any]:
    require(isinstance(request, dict), "request must be an object")
    _validate_schema(request, REQUEST_SCHEMA_PATH, "request")
    assert_oracle_blind_request(request)
    expected_profile_digest = digest_value(request["protected_relation_profile"])
    require(
        request["protected_relation_profile_digest"] == expected_profile_digest,
        "PROTECTED_RELATION_PROFILE_DIGEST_MISMATCH",
    )
    canonical_json_bytes(request)
    return request


def _v0_inventory_entries() -> dict[str, dict[str, Any]]:
    raw = V0_INVENTORY_PATH.read_bytes()
    require(digest_bytes(raw) == V0_INVENTORY_SHA256, "V0_INVENTORY_IDENTITY_MISMATCH")
    try:
        inventory = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise AdapterContractViolation(f"invalid v0 inventory: {exc}") from exc
    return {entry["path"]: entry for entry in inventory["entries"]}


def validate_frozen_v0_request_binding(request: dict[str, Any]) -> dict[str, Any]:
    validate_request(request)
    relative_path = f"corpus/v0/challenge/cases/{request['challenge_id']}.json"
    entry = _v0_inventory_entries().get(relative_path)
    require(entry is not None, "REQUEST_NOT_A_FROZEN_V0_CHALLENGE")
    challenge_path = ROOT / relative_path
    require(challenge_path.is_file(), "FROZEN_V0_CHALLENGE_MISSING")
    raw = challenge_path.read_bytes()
    require(len(raw) == entry["byte_length"], "FROZEN_V0_CHALLENGE_LENGTH_MISMATCH")
    exact_digest = digest_bytes(raw)
    require(exact_digest == entry["sha256"], "FROZEN_V0_CHALLENGE_DIGEST_MISMATCH")
    require(request["challenge_digest"] == exact_digest, "REQUEST_CHALLENGE_DIGEST_MISMATCH")
    challenge = _validate_challenge_bytes(raw, challenge_path)
    require(challenge["fixture_id"] == request["challenge_id"], "REQUEST_CHALLENGE_ID_MISMATCH")
    require(
        challenge["protected_relation"] == request["protected_relation_profile"],
        "REQUEST_PROTECTED_RELATION_MISMATCH",
    )
    require(
        {"before": challenge["before"], "after": challenge["after"]} == request["evaluation_input"],
        "REQUEST_EVALUATION_INPUT_MISMATCH",
    )
    return request


def _validate_challenge_bytes(raw: bytes, path: Path) -> dict[str, Any]:
    require(bool(raw), f"empty challenge: {path}")
    require(not raw.startswith(b"\xef\xbb\xbf"), f"challenge BOM forbidden: {path}")
    require(b"\r" not in raw and b"\x00" not in raw, f"invalid challenge framing: {path}")
    require(raw.endswith(b"\n") and not raw.endswith(b"\n\n"), f"challenge final LF mismatch: {path}")
    try:
        challenge = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise AdapterContractViolation(f"invalid challenge JSON: {path}: {exc}") from exc
    require(isinstance(challenge, dict), "challenge must be an object")
    require(
        set(challenge) == {"schema", "fixture_id", "class", "protected_relation", "before", "after"},
        "CHALLENGE_FIELD_SET_MISMATCH",
    )
    for _, key, _ in _walk(challenge):
        if key is not None:
            require(key.lower() not in BANNED_CHALLENGE_EXTRA_KEYS, f"ORACLE_LEAKAGE_IN_CHALLENGE:{key}")
    return challenge


def build_request(
    challenge_path: Path,
    *,
    evaluator_id: str,
    evaluator_version: str,
    config_digest: str,
    execution_metadata: dict[str, str] | None = None,
    claimed_challenge_digest: str | None = None,
) -> dict[str, Any]:
    raw = challenge_path.read_bytes()
    actual_challenge_digest = digest_bytes(raw)
    if claimed_challenge_digest is not None:
        require(claimed_challenge_digest == actual_challenge_digest, "CHALLENGE_DIGEST_CLAIM_MISMATCH")
    challenge = _validate_challenge_bytes(raw, challenge_path)
    profile = challenge["protected_relation"]
    request: dict[str, Any] = {
        "schema": "protected-relation-external-adapter-request.v0",
        "adapter_contract_version": "v0",
        "challenge_id": challenge["fixture_id"],
        "challenge_digest": actual_challenge_digest,
        "protected_relation_profile": profile,
        "protected_relation_profile_digest": digest_value(profile),
        "evaluator": {
            "id": evaluator_id,
            "version": evaluator_version,
            "config_digest": config_digest,
        },
        "evaluation_input": {
            "before": challenge["before"],
            "after": challenge["after"],
        },
    }
    if execution_metadata is not None:
        request["execution_metadata"] = execution_metadata
    return validate_request(request)


def validate_evaluator_output(evaluator_output: Any) -> dict[str, Any]:
    require(isinstance(evaluator_output, dict), "evaluator output must be an object")
    _validate_schema(evaluator_output, EVALUATOR_OUTPUT_SCHEMA_PATH, "evaluator output")
    canonical_json_bytes(evaluator_output)
    return evaluator_output


def invocation_context_for(
    request: dict[str, Any],
    command: list[str],
    *,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    validate_request(request)
    require(bool(command), "adapter command is empty")
    require(all(isinstance(part, str) and part for part in command), "invalid adapter command")
    require(metadata is None or isinstance(metadata, dict), "invalid invocation metadata")
    context = {
        "schema": "protected-relation-external-adapter-invocation.v0",
        "request_digest": digest_value(request),
        "evaluator": request["evaluator"],
        "command": list(command),
        "metadata": metadata or {},
    }
    canonical_json_bytes(context)
    return context


def _validate_invocation_context(request: dict[str, Any], context: Any) -> dict[str, Any]:
    require(isinstance(context, dict), "invocation context must be an object")
    require(
        set(context) == {"schema", "request_digest", "evaluator", "command", "metadata"},
        "INVALID_INVOCATION_CONTEXT_FIELDS",
    )
    require(
        context["schema"] == "protected-relation-external-adapter-invocation.v0",
        "INVALID_INVOCATION_CONTEXT_SCHEMA",
    )
    require(
        context["request_digest"] == digest_value(request),
        "EVALUATOR_OUTPUT_REPLAY_REQUEST_MISMATCH",
    )
    require(context["evaluator"] == request["evaluator"], "INVOCATION_EVALUATOR_IDENTITY_MISMATCH")
    command = context["command"]
    require(
        isinstance(command, list) and bool(command) and all(isinstance(part, str) and part for part in command),
        "INVALID_INVOCATION_COMMAND",
    )
    require(isinstance(context["metadata"], dict), "INVALID_INVOCATION_METADATA")
    canonical_json_bytes(context)
    return context


def validate_response(request: dict[str, Any], response: Any) -> dict[str, Any]:
    validate_request(request)
    require(isinstance(response, dict), "response must be an object")
    _validate_schema(response, RESPONSE_SCHEMA_PATH, "response")
    require(response["adapter_status"] == "RESPONSE_VALID", "RESPONSE_ADAPTER_STATUS_MISMATCH")
    require(response["request_digest"] == digest_value(request), "RESPONSE_REQUEST_DIGEST_MISMATCH")
    require(response["challenge_id"] == request["challenge_id"], "RESPONSE_CHALLENGE_ID_MISMATCH")
    require(response["challenge_digest"] == request["challenge_digest"], "RESPONSE_CHALLENGE_DIGEST_MISMATCH")
    require(
        response["protected_relation_profile_digest"]
        == request["protected_relation_profile_digest"],
        "RESPONSE_PROTECTED_RELATION_DIGEST_MISMATCH",
    )
    require(response["evaluator"] == request["evaluator"], "RESPONSE_EVALUATOR_IDENTITY_MISMATCH")
    if request["challenge_id"] not in SUPPORTED_CHALLENGE_IDS:
        require(
            response["outcome"] == "UNVERIFIABLE",
            "UNSUPPORTED_CHALLENGE_UPGRADED_TO_SEMANTIC_CLAIM",
        )
    canonical_json_bytes(response)
    return response


def validate_response_binding(
    request: dict[str, Any],
    response: dict[str, Any],
    evaluator_output: dict[str, Any],
    invocation_context: dict[str, Any],
) -> dict[str, Any]:
    response = validate_response(request, response)
    evaluator_output = validate_evaluator_output(evaluator_output)
    invocation_context = _validate_invocation_context(request, invocation_context)
    require(
        response["evaluator_output_digest"] == digest_value(evaluator_output),
        "RESPONSE_EVALUATOR_OUTPUT_DIGEST_MISMATCH",
    )
    require(
        response["invocation_digest"] == digest_value(invocation_context),
        "RESPONSE_INVOCATION_DIGEST_MISMATCH",
    )
    require(response["outcome"] == evaluator_output["outcome"], "RESPONSE_OUTCOME_BINDING_MISMATCH")
    require(
        response["reason_detail"] == evaluator_output["reason_detail"],
        "RESPONSE_REASON_DETAIL_BINDING_MISMATCH",
    )
    return response


def bind_evaluator_output(
    request: dict[str, Any],
    evaluator_output: dict[str, Any],
    invocation_context: dict[str, Any],
) -> dict[str, Any]:
    validate_request(request)
    evaluator_output = validate_evaluator_output(evaluator_output)
    invocation_context = _validate_invocation_context(request, invocation_context)
    response = {
        "schema": "protected-relation-external-adapter-response.v0",
        "adapter_status": "RESPONSE_VALID",
        "request_digest": digest_value(request),
        "challenge_id": request["challenge_id"],
        "challenge_digest": request["challenge_digest"],
        "protected_relation_profile_digest": request["protected_relation_profile_digest"],
        "evaluator": request["evaluator"],
        "evaluator_output_digest": digest_value(evaluator_output),
        "invocation_digest": digest_value(invocation_context),
        "outcome": evaluator_output["outcome"],
        "reason_code": "EVALUATOR_JUDGMENT",
        "reason_detail": evaluator_output["reason_detail"],
        "evidence": [],
    }
    return validate_response_binding(request, response, evaluator_output, invocation_context)


def _transcript(
    request: dict[str, Any],
    invocation_context: dict[str, Any],
    status: str,
    *,
    raw_response_bytes: bytes,
    stderr_bytes: bytes,
    exit_code: int | None,
    normalized_response: dict[str, Any] | None,
    evaluator_output: dict[str, Any] | None,
    detail: str,
    recorded_at: str | None,
) -> dict[str, Any]:
    require(status in ADAPTER_STATUSES, f"unknown adapter status: {status}")
    raw_response = raw_response_bytes.decode("utf-8", errors="replace")
    stderr = stderr_bytes.decode("utf-8", errors="replace")
    return {
        "schema": "protected-relation-external-adapter-transcript.v0",
        "request_digest": digest_value(request),
        "response_digest": digest_value(normalized_response) if normalized_response is not None else None,
        "evaluator_output_digest": digest_value(evaluator_output) if evaluator_output is not None else None,
        "raw_response_digest": digest_bytes(raw_response_bytes),
        "raw_response_base64": base64.b64encode(raw_response_bytes).decode("ascii"),
        "stderr_digest": digest_bytes(stderr_bytes),
        "stderr_base64": base64.b64encode(stderr_bytes).decode("ascii"),
        "evaluator": request["evaluator"],
        "invocation": invocation_context,
        "invocation_digest": digest_value(invocation_context),
        "recorded_at": recorded_at or datetime.now(timezone.utc).isoformat(),
        "timestamp_authoritative": False,
        "raw_response": raw_response,
        "stderr": stderr,
        "normalized_response": normalized_response,
        "evaluator_output": evaluator_output,
        "adapter_status": status,
        "adapter_detail": detail,
        "exit_code": exit_code,
    }


def run_command_adapter(
    request: dict[str, Any],
    command: list[str],
    *,
    timeout_seconds: float = 30.0,
    recorded_at: str | None = None,
    invocation_metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    validate_request(request)
    invocation_context = invocation_context_for(request, command, metadata=invocation_metadata)
    payload = canonical_json_bytes(request) + b"\n"
    try:
        process = subprocess.run(
            command,
            input=payload,
            capture_output=True,
            check=False,
            timeout=timeout_seconds,
        )
    except subprocess.TimeoutExpired as exc:
        raw = exc.stdout or b""
        stderr = exc.stderr or b""
        return _transcript(
            request,
            invocation_context,
            "TIMEOUT",
            raw_response_bytes=raw,
            stderr_bytes=stderr,
            exit_code=None,
            normalized_response=None,
            evaluator_output=None,
            detail="adapter process exceeded timeout",
            recorded_at=recorded_at,
        )
    except OSError as exc:
        return _transcript(
            request,
            invocation_context,
            "PROCESS_ERROR",
            raw_response_bytes=b"",
            stderr_bytes=str(exc).encode("utf-8", errors="replace"),
            exit_code=None,
            normalized_response=None,
            evaluator_output=None,
            detail="adapter process could not start",
            recorded_at=recorded_at,
        )

    raw_response_bytes = process.stdout
    stderr_bytes = process.stderr
    raw_response = raw_response_bytes.decode("utf-8", errors="replace")
    if process.returncode != 0:
        return _transcript(
            request,
            invocation_context,
            "PROCESS_ERROR",
            raw_response_bytes=raw_response_bytes,
            stderr_bytes=stderr_bytes,
            exit_code=process.returncode,
            normalized_response=None,
            evaluator_output=None,
            detail="adapter process exited nonzero",
            recorded_at=recorded_at,
        )
    if not raw_response.strip():
        return _transcript(
            request,
            invocation_context,
            "EMPTY_RESPONSE",
            raw_response_bytes=raw_response_bytes,
            stderr_bytes=stderr_bytes,
            exit_code=process.returncode,
            normalized_response=None,
            evaluator_output=None,
            detail="adapter returned no response",
            recorded_at=recorded_at,
        )
    try:
        parsed = json.loads(raw_response)
    except json.JSONDecodeError as exc:
        return _transcript(
            request,
            invocation_context,
            "MALFORMED_RESPONSE",
            raw_response_bytes=raw_response_bytes,
            stderr_bytes=stderr_bytes,
            exit_code=process.returncode,
            normalized_response=None,
            evaluator_output=None,
            detail=f"adapter response is not JSON: {exc}",
            recorded_at=recorded_at,
        )
    try:
        evaluator_output = validate_evaluator_output(parsed)
        normalized = bind_evaluator_output(request, evaluator_output, invocation_context)
    except AdapterContractViolation as exc:
        return _transcript(
            request,
            invocation_context,
            "INVALID_EVALUATOR_OUTPUT",
            raw_response_bytes=raw_response_bytes,
            stderr_bytes=stderr_bytes,
            exit_code=process.returncode,
            normalized_response=None,
            evaluator_output=None,
            detail=str(exc),
            recorded_at=recorded_at,
        )
    return _transcript(
        request,
        invocation_context,
        "RESPONSE_VALID",
        raw_response_bytes=raw_response_bytes,
        stderr_bytes=stderr_bytes,
        exit_code=process.returncode,
        normalized_response=normalized,
        evaluator_output=evaluator_output,
        detail="response validated",
        recorded_at=recorded_at,
    )
