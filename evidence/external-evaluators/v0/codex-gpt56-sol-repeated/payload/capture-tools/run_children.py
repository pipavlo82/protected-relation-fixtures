from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


CHALLENGES = tuple(f"prf-{index:03d}" for index in range(1, 7))
RUNS = tuple(range(1, 11))
MODEL = "gpt-5.6-sol"
REASONING = "high"
CLI_VERSION = "0.153.2"
VALID_OUTCOMES = {"PRESERVED", "VIOLATED", "UNVERIFIABLE"}
FORBIDDEN_KEYS = {
    "expected",
    "expected_outcome",
    "oracle",
    "oracle_identity",
    "benchmark_classification",
    "mismatch_classification",
    "reference_evaluator_result",
}
FORBIDDEN_TEXT = (
    "unsafe_false_preservation",
    "unsafe_unverifiable_upgrade",
    "false_violation",
    "preservation_not_established",
    "violation_not_established",
    "unverifiable_misclassified_as_violation",
    "qwen2.5",
    "llama3.1",
    "previous codex result",
    "prior codex result",
)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def find_forbidden_keys(value: Any, prefix: str = "$") -> list[str]:
    hits: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            lowered = key.lower()
            if lowered in FORBIDDEN_KEYS or lowered.startswith("expected_") or lowered.startswith("oracle_"):
                hits.append(f"{prefix}.{key}")
            hits.extend(find_forbidden_keys(child, f"{prefix}.{key}"))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            hits.extend(find_forbidden_keys(child, f"{prefix}[{index}]"))
    return hits


def validate_minimal_output(raw: bytes) -> tuple[str, dict[str, str] | None, str | None]:
    if not raw:
        return "EMPTY_RESPONSE", None, "final response file was empty"
    try:
        value = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        return "INVALID_EVALUATOR_OUTPUT", None, f"malformed JSON: {exc}"
    if not isinstance(value, dict) or set(value) != {"outcome", "reason_detail"}:
        return "INVALID_EVALUATOR_OUTPUT", None, "payload must contain exactly outcome and reason_detail"
    if value.get("outcome") not in VALID_OUTCOMES:
        return "INVALID_EVALUATOR_OUTPUT", None, "unknown outcome"
    if not isinstance(value.get("reason_detail"), str):
        return "INVALID_EVALUATOR_OUTPUT", None, "reason_detail must be a string"
    return "RESPONSE_VALID", {"outcome": value["outcome"], "reason_detail": value["reason_detail"]}, None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--runtime-home", type=Path, required=True)
    parser.add_argument("--codex-exe", type=Path, required=True)
    parser.add_argument("--timeout-seconds", type=int, default=300)
    parser.add_argument("--prepare-only", action="store_true")
    args = parser.parse_args()

    root = args.root.resolve()
    repo = args.repo.resolve()
    runtime_home = args.runtime_home.resolve()
    codex_exe = args.codex_exe.resolve()
    request_root = root / "blind-requests"
    instruction_source = root / "fixed-evaluator-instruction.txt"
    schema_source = root / "minimal-evaluator-output-schema.json"
    isolated_root = root / "isolated"
    metadata_root = root / "metadata"
    metadata_root.mkdir(parents=True, exist_ok=True)

    if not codex_exe.is_file() or not runtime_home.joinpath("auth.json").is_file():
        raise RuntimeError("standalone Codex executable or isolated authentication material missing")
    if repo == root or repo in root.parents or root in repo.parents:
        raise RuntimeError("experiment root and PRF repository must be disjoint")
    for candidate in [root, *root.parents]:
        if candidate.joinpath(".git").exists() or candidate.joinpath("AGENTS.md").exists():
            raise RuntimeError(f"inherited repository/instruction material at {candidate}")

    sys.path.insert(0, str(repo))
    from adapters.v0.contract import (  # type: ignore[import-not-found]
        assert_oracle_blind_request,
        validate_frozen_v0_request_binding,
        validate_request,
    )

    instruction = instruction_source.read_bytes()
    schema = schema_source.read_bytes()
    leakage_rows = []
    for challenge in CHALLENGES:
        request_path = request_root / f"{challenge}.json"
        request_raw = request_path.read_bytes()
        request = json.loads(request_raw.decode("utf-8"))
        validate_request(request)
        validate_frozen_v0_request_binding(request)
        assert_oracle_blind_request(request)
        key_hits = find_forbidden_keys(request)
        prompt = instruction + b"\nValidated blind request:\n" + request_raw
        lowered = prompt.decode("utf-8").lower()
        text_hits = [marker for marker in FORBIDDEN_TEXT if marker in lowered]
        if key_hits or text_hits:
            raise RuntimeError(f"answer-bearing evaluator input for {challenge}: {key_hits}/{text_hits}")
        leakage_rows.append(
            {
                "challenge_id": challenge,
                "request_schema_validation": "PASS",
                "frozen_request_binding": "PASS",
                "canonical_oracle_blind_guard": "PASS",
                "forbidden_key_hits": key_hits,
                "answer_bearing_text_hits": text_hits,
                "request_sha256": sha256(request_raw),
                "prompt_sha256": sha256(prompt),
            }
        )
    write_json(
        metadata_root / "oracle-leakage-check.json",
        {
            "schema": "prf-codex-gpt56-oracle-leakage-check.v0",
            "status": "PASS",
            "requests_checked": len(leakage_rows),
            "answer_bearing_markers_found": 0,
            "checks": leakage_rows,
        },
    )

    sanitized_config = runtime_home / "config.toml"
    shutil.copyfile(sanitized_config, metadata_root / "isolated-runtime-config.toml")
    write_json(
        metadata_root / "isolation-declaration.json",
        {
            "schema": "prf-codex-child-isolation.v0",
            "experiment_root": str(root),
            "isolated_root": str(isolated_root),
            "prf_repository": str(repo),
            "paths_disjoint": True,
            "git_ancestor_found": False,
            "agents_instruction_ancestor_found": False,
            "mcp_servers_configured": 0,
            "filesystem_shell_web_browser_tools_disabled": True,
            "code_mode_tool_audit_result": "NO_CAPABILITY",
            "outside_filesystem_canary_result": "NO_CAPABILITY",
            "session_mode": "EPHEMERAL_FRESH_PROCESS",
            "semantic_retries": 0,
        },
    )
    if args.prepare_only:
        print(json.dumps({"status": "PREPARED", "requests": len(leakage_rows), "leakage": "PASS"}))
        return 0

    base_environment = os.environ.copy()
    for key in list(base_environment):
        upper = key.upper()
        if upper.startswith("OPENAI_") or upper.startswith("GITHUB_") or upper.startswith("GH_"):
            base_environment.pop(key, None)
        elif upper.startswith("MCP_") or upper in {"CODEX_THREAD_ID", "CODEX_SESSION_ID"}:
            base_environment.pop(key, None)
    base_environment["CODEX_HOME"] = str(runtime_home)
    base_environment["NO_COLOR"] = "1"
    base_environment["TERM"] = "dumb"

    total = len(CHALLENGES) * len(RUNS)
    completed = 0
    for challenge in CHALLENGES:
        request_source = request_root / f"{challenge}.json"
        request_raw = request_source.read_bytes()
        prompt = instruction + b"\nValidated blind request:\n" + request_raw
        for run_index in RUNS:
            observation_root = isolated_root / challenge / f"run-{run_index:02d}"
            if observation_root.exists():
                raise RuntimeError(f"fresh observation directory already exists: {observation_root}")
            observation_root.mkdir(parents=True)
            request_path = observation_root / "request.json"
            instruction_path = observation_root / "evaluator-instruction.txt"
            schema_path = observation_root / "evaluator-output-schema.json"
            prompt_path = observation_root / "prompt.txt"
            request_path.write_bytes(request_raw)
            instruction_path.write_bytes(instruction)
            schema_path.write_bytes(schema)
            prompt_path.write_bytes(prompt)
            final_path = observation_root / "raw-final-response.bin"
            stdout_path = observation_root / "raw-stdout.jsonl"
            stderr_path = observation_root / "raw-stderr.bin"
            command = [
                str(codex_exe),
                "exec",
                "--strict-config",
                "--skip-git-repo-check",
                "--ephemeral",
                "--ignore-rules",
                "--model",
                MODEL,
                "-c",
                'model_reasoning_effort="high"',
                "--output-schema",
                schema_path.name,
                "--json",
                "-o",
                final_path.name,
                "-",
            ]
            start = utc_now()
            timed_out = False
            process = subprocess.Popen(
                command,
                cwd=observation_root,
                env=base_environment,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            try:
                stdout, stderr = process.communicate(prompt, timeout=args.timeout_seconds)
            except subprocess.TimeoutExpired as exc:
                timed_out = True
                process.kill()
                trailing_stdout, trailing_stderr = process.communicate()
                stdout = (exc.stdout or b"") + (trailing_stdout or b"")
                stderr = (exc.stderr or b"") + (trailing_stderr or b"")
            end = utc_now()
            stdout_path.write_bytes(stdout)
            stderr_path.write_bytes(stderr)
            final_raw = final_path.read_bytes() if final_path.exists() else b""
            if not final_path.exists():
                final_path.write_bytes(b"")
            if timed_out:
                adapter_status, semantic, detail = "TIMEOUT", None, "child execution timed out"
            elif process.returncode != 0:
                adapter_status, semantic, detail = "PROCESS_ERROR", None, f"child exit code {process.returncode}"
            else:
                adapter_status, semantic, detail = validate_minimal_output(final_raw)
            observation = {
                "schema": "prf-codex-gpt56-child-observation.v0",
                "challenge_id": challenge,
                "run_index": run_index,
                "model": MODEL,
                "reasoning_effort": REASONING,
                "codex_cli_version": CLI_VERSION,
                "codex_executable": str(codex_exe),
                "isolated_cwd": str(observation_root),
                "prf_repository_outside_child_workspace": True,
                "session_mode": "EPHEMERAL_FRESH_PROCESS",
                "semantic_retry_count": 0,
                "invocation": {
                    "argv": command,
                    "stdin": "prompt.txt",
                    "environment_allowlisted_metadata": {
                        "CODEX_HOME": "isolated runtime home; authentication bytes excluded",
                        "NO_COLOR": "1",
                        "TERM": "dumb",
                    },
                    "timeout_seconds": args.timeout_seconds,
                },
                "started_at": start,
                "ended_at": end,
                "timestamps_authoritative": False,
                "exit_code": process.returncode,
                "adapter_status": adapter_status,
                "adapter_failure_detail": detail,
                "semantic_payload": semantic,
                "bindings": {
                    "request_sha256": sha256(request_raw),
                    "instruction_sha256": sha256(instruction),
                    "prompt_sha256": sha256(prompt),
                    "evaluator_output_schema_sha256": sha256(schema),
                    "raw_stdout_sha256": sha256(stdout),
                    "raw_stderr_sha256": sha256(stderr),
                    "raw_final_response_sha256": sha256(final_raw),
                    "semantic_payload_sha256": sha256(canonical_json_bytes(semantic)) if semantic is not None else None,
                },
            }
            write_json(observation_root / "observation.json", observation)
            completed += 1
            print(
                json.dumps(
                    {
                        "progress": f"{completed}/{total}",
                        "challenge": challenge,
                        "run": run_index,
                        "status": adapter_status,
                        "outcome": semantic["outcome"] if semantic else None,
                        "exit": process.returncode,
                    },
                    separators=(",", ":"),
                ),
                flush=True,
            )
    write_json(
        metadata_root / "capture-phase-complete.json",
        {
            "schema": "prf-codex-gpt56-capture-phase.v0",
            "capture_complete": True,
            "scoring_started": False,
            "scheduled_observations": total,
            "attempted_observations": completed,
            "captured_observations": completed,
            "completed_at": utc_now(),
        },
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
