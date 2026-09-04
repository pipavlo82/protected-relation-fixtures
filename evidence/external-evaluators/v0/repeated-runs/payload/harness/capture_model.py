from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from typing import Any

from common import (
    CHALLENGE_IDS,
    MODEL_KEYS,
    MODEL_SPECS,
    REPO,
    ROOT,
    RUN_INDICES,
    digest_value,
    load_json,
    observation_root,
    sha256_bytes,
    write_json,
)


sys.path.insert(0, str(REPO))
from adapters.v0.contract import (  # noqa: E402
    AdapterContractViolation,
    bind_evaluator_output,
    invocation_context_for,
    validate_evaluator_output,
    validate_request,
)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def server_responding() -> bool:
    try:
        result = subprocess.run(
            ["wsl.exe", "-d", "Ubuntu", "--", "/usr/local/bin/ollama", "list"],
            capture_output=True,
            timeout=20,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return result.returncode == 0


def restart_server(after_observation: str) -> dict[str, Any]:
    restart_root = ROOT / "metadata/server-restarts"
    restart_root.mkdir(parents=True, exist_ok=True)
    attempt = len(list(restart_root.glob("*.json"))) + 1
    log_path = restart_root / f"restart-{attempt:02d}.log.bin"
    log_handle = log_path.open("wb")
    flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    process = subprocess.Popen(
        ["wsl.exe", "-d", "Ubuntu", "--", "/usr/local/bin/ollama", "serve"],
        stdout=log_handle,
        stderr=subprocess.STDOUT,
        creationflags=flags,
    )
    log_handle.close()
    started_at = utc_now()
    responding = False
    for _ in range(60):
        if server_responding():
            responding = True
            break
        time.sleep(1)
    record = {
        "schema": "prf-ollama-server-restart.v0",
        "attempt": attempt,
        "after_observation": after_observation,
        "windows_process_id": process.pid,
        "started_at": started_at,
        "timestamp_authoritative": False,
        "server_responding": responding,
        "log_path": log_path.relative_to(ROOT).as_posix(),
    }
    write_json(restart_root / f"restart-{attempt:02d}.json", record)
    return record


def make_transcript(
    request: dict[str, Any],
    invocation: dict[str, Any],
    *,
    status: str,
    stdout: bytes,
    stderr: bytes,
    exit_code: int | None,
    evaluator_output: dict[str, Any] | None,
    response: dict[str, Any] | None,
    detail: str,
    recorded_at: str,
) -> dict[str, Any]:
    return {
        "schema": "protected-relation-external-adapter-transcript.v0",
        "request_digest": digest_value(request),
        "response_digest": digest_value(response) if response is not None else None,
        "evaluator_output_digest": digest_value(evaluator_output) if evaluator_output is not None else None,
        "raw_response_digest": sha256_bytes(stdout),
        "stderr_digest": sha256_bytes(stderr),
        "evaluator": request["evaluator"],
        "invocation": invocation,
        "invocation_digest": digest_value(invocation),
        "recorded_at": recorded_at,
        "timestamp_authoritative": False,
        "normalized_response": response,
        "evaluator_output": evaluator_output,
        "adapter_status": status,
        "adapter_detail": detail,
        "exit_code": exit_code,
    }


def capture_observation(model_key: str, challenge_id: str, run_index: int) -> dict[str, Any]:
    spec = MODEL_SPECS[model_key]
    target = observation_root(model_key, challenge_id, run_index)
    if target.exists():
        raise RuntimeError(f"observation already exists: {target}")
    target.mkdir(parents=True)
    template = ROOT / "metadata/templates" / model_key
    request_bytes = (template / f"{challenge_id}.request.json").read_bytes()
    prompt = (template / f"{challenge_id}.prompt.txt").read_bytes()
    (target / "request.json").write_bytes(request_bytes)
    (target / "prompt.txt").write_bytes(prompt)
    request = json.loads(request_bytes.decode("utf-8"))
    validate_request(request)
    command = [
        "wsl.exe",
        "-d",
        "Ubuntu",
        "--",
        "env",
        "OLLAMA_NOHISTORY=1",
        "/usr/local/bin/ollama",
        "run",
        spec["model"],
        "--format",
        "json",
        "--hidethinking",
        "--keepalive",
        "0",
        prompt.decode("utf-8"),
    ]
    invocation = invocation_context_for(
        request,
        command,
        metadata={
            "study": "prf-repeated-runs-v0",
            "model_key": model_key,
            "challenge_id": challenge_id,
            "run_index": run_index,
            "request_bytes_sha256": sha256_bytes(request_bytes),
            "prompt_sha256": sha256_bytes(prompt),
            "semantic_retry": False,
        },
    )
    write_json(target / "invocation-context.json", invocation)
    started_at = utc_now()
    status = "PROCESS_ERROR"
    stdout = b""
    stderr = b""
    exit_code: int | None = None
    detail = "adapter process could not start"
    try:
        process = subprocess.run(command, capture_output=True, check=False, timeout=300)
        stdout = process.stdout
        stderr = process.stderr
        exit_code = process.returncode
        if process.returncode != 0:
            status = "PROCESS_ERROR"
            detail = "adapter process exited nonzero"
        elif not stdout.strip():
            status = "EMPTY_RESPONSE"
            detail = "adapter returned no response"
        else:
            status = "PENDING_PARSE"
            detail = "raw output captured"
    except subprocess.TimeoutExpired as exc:
        stdout = exc.stdout or b""
        stderr = exc.stderr or b""
        status = "TIMEOUT"
        detail = "adapter process exceeded timeout"
    except OSError as exc:
        stderr = str(exc).encode("utf-8", errors="replace")
        status = "PROCESS_ERROR"
        detail = "adapter process could not start"

    # Raw bytes are persisted before decoding, parsing, schema validation, or wrapping.
    (target / "stdout.bin").write_bytes(stdout)
    (target / "stderr.bin").write_bytes(stderr)

    evaluator_output = None
    response = None
    if status == "PENDING_PARSE":
        try:
            parsed = json.loads(stdout.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            status = "MALFORMED_RESPONSE"
            detail = f"adapter response is not valid UTF-8 JSON: {exc}"
        else:
            try:
                evaluator_output = validate_evaluator_output(parsed)
                response = bind_evaluator_output(request, evaluator_output, invocation)
            except AdapterContractViolation as exc:
                evaluator_output = None
                response = None
                status = "INVALID_EVALUATOR_OUTPUT"
                detail = str(exc)
            else:
                status = "RESPONSE_VALID"
                detail = "evaluator semantic payload validated and deterministically wrapped"
                write_json(target / "evaluator-output.json", evaluator_output)
                write_json(target / "wrapped-response.json", response)

    ended_at = utc_now()
    transcript = make_transcript(
        request,
        invocation,
        status=status,
        stdout=stdout,
        stderr=stderr,
        exit_code=exit_code,
        evaluator_output=evaluator_output,
        response=response,
        detail=detail,
        recorded_at=ended_at,
    )
    write_json(target / "transcript.json", transcript)
    observation = {
        "schema": "prf-external-evaluator-repeated-observation.v0",
        "study": "prf-repeated-runs-v0",
        "model_key": model_key,
        "model": spec["model"],
        "model_id": spec["model_id"],
        "model_payload_sha256": spec["payload_sha256"],
        "ollama_version": "0.15.2",
        "challenge_id": challenge_id,
        "run_index": run_index,
        "request_bytes_sha256": sha256_bytes(request_bytes),
        "request_digest": digest_value(request),
        "prompt_sha256": sha256_bytes(prompt),
        "stdout_sha256": sha256_bytes(stdout),
        "stderr_sha256": sha256_bytes(stderr),
        "exit_code": exit_code,
        "adapter_status": status,
        "semantic_outcome": evaluator_output["outcome"] if evaluator_output else None,
        "evaluator_output_digest": digest_value(evaluator_output) if evaluator_output else None,
        "wrapped_response_digest": digest_value(response) if response else None,
        "invocation_context_digest": digest_value(invocation),
        "started_at": started_at,
        "ended_at": ended_at,
        "timestamps_authoritative": False,
        "semantic_retries": 0,
    }
    if status in {"PROCESS_ERROR", "TIMEOUT"} and not server_responding():
        observation["server_restart_after_observation"] = restart_server(
            f"{model_key}/{challenge_id}/run-{run_index:02d}"
        )
    write_json(target / "observation.json", observation)
    return observation


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("model_key", choices=MODEL_KEYS)
    args = parser.parse_args()
    model_key = args.model_key
    order_index = MODEL_KEYS.index(model_key)
    for earlier in MODEL_KEYS[:order_index]:
        block = ROOT / f"metadata/model-blocks/{earlier}.json"
        if not block.is_file() or load_json(block).get("capture_complete") is not True:
            raise RuntimeError(f"earlier model block is incomplete: {earlier}")
    if (ROOT / f"metadata/model-blocks/{model_key}.json").exists():
        raise RuntimeError(f"model block already finalized: {model_key}")
    identities = load_json(ROOT / "metadata/model-identities.json")["models"]
    identity = next(row for row in identities if row["model_key"] == model_key)
    if identity["available"] is not True:
        write_json(
            ROOT / f"metadata/model-blocks/{model_key}.json",
            {
                "schema": "prf-repeated-model-block.v0",
                "model_key": model_key,
                "available": False,
                "capture_complete": True,
                "scheduled": 0,
                "attempted": 0,
                "captured": 0,
            },
        )
        print(json.dumps({"model_key": model_key, "status": "UNAVAILABLE"}), flush=True)
        return 0

    summaries = []
    for challenge_id in CHALLENGE_IDS:
        for run_index in RUN_INDICES:
            observation = capture_observation(model_key, challenge_id, run_index)
            summaries.append(observation)
            print(
                json.dumps(
                    {
                        "progress": len(summaries),
                        "of": 60,
                        "model_key": model_key,
                        "challenge_id": challenge_id,
                        "run_index": run_index,
                        "adapter_status": observation["adapter_status"],
                        "semantic_outcome": observation["semantic_outcome"],
                    },
                    separators=(",", ":"),
                ),
                flush=True,
            )
    valid = sum(row["adapter_status"] == "RESPONSE_VALID" for row in summaries)
    write_json(
        ROOT / f"metadata/model-blocks/{model_key}.json",
        {
            "schema": "prf-repeated-model-block.v0",
            "model_key": model_key,
            "available": True,
            "capture_complete": len(summaries) == 60,
            "scheduled": 60,
            "attempted": len(summaries),
            "captured": len(summaries),
            "valid_semantic_responses": valid,
            "adapter_failures": len(summaries) - valid,
            "status_counts": {
                status: sum(row["adapter_status"] == status for row in summaries)
                for status in sorted({row["adapter_status"] for row in summaries})
            },
        },
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
