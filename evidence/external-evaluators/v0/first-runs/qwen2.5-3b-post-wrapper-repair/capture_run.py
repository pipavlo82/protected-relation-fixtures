from __future__ import annotations

from datetime import datetime, timezone
import base64
import hashlib
import json
from pathlib import Path
import sys


REPO = Path(
    r"C:\Users\msi\Documents\Codex\2026-08-25\we-are-closing-the-erc-8309"
    r"\protected-relation-fixtures"
)
ROOT = Path(r"D:\prf-experiments\qwen2.5-3b-instruct-post-wrapper-repair")
ORIGINAL = Path(r"D:\prf-experiments\qwen2.5-3b-instruct-first-run")
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(ROOT))

from adapters.v0.contract import (  # noqa: E402
    CHALLENGE_ROOT,
    assert_oracle_blind_request,
    build_request,
    canonical_json_bytes,
    digest_value,
    run_command_adapter,
    validate_request,
)
from qwen_evaluator import MODEL, make_prompt  # noqa: E402


OLLAMA_VERSION = "0.15.2"
MODEL_ID = "357c53fb659c"
MODEL_BLOB_DIGEST = "sha256:5ee4f07cdb9beadbbb293e85803c569b01bd37ed059d2715faa7bb405f31caa6"
EXPECTED_IDS = [f"prf-{index:03d}" for index in range(1, 7)]
CONFIG = {
    "provider": "local-wsl-ollama",
    "wsl_distro": "Ubuntu",
    "ollama_path": "/usr/local/bin/ollama",
    "ollama_version": OLLAMA_VERSION,
    "model": MODEL,
    "model_id": MODEL_ID,
    "model_blob_digest": MODEL_BLOB_DIGEST,
    "environment": {"OLLAMA_NOHISTORY": "1"},
    "ollama_flags": ["--format", "json", "--hidethinking", "--keepalive", "0"],
    "retry_policy": "NO_RETRY_ONE_CALL_PER_CHALLENGE",
}
BANNED_JSON_KEYS = {
    "expected",
    "expected_outcome",
    "oracle",
    "oracle_result",
    "benchmark_result",
    "mismatch_classification",
    "reference_evaluator_result",
}
BANNED_VALUES = {
    "UNSAFE_FALSE_PRESERVATION",
    "UNSAFE_UNVERIFIABLE_UPGRADE",
    "FALSE_VIOLATION",
    "PRESERVATION_NOT_ESTABLISHED",
    "VIOLATION_NOT_ESTABLISHED",
    "UNVERIFIABLE_MISCLASSIFIED_AS_VIOLATION",
}


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")


def file_inventory(root: Path) -> list[dict[str, object]]:
    rows = []
    for path in sorted((item for item in root.rglob("*") if item.is_file()), key=lambda item: item.as_posix()):
        raw = path.read_bytes()
        rows.append(
            {
                "path": path.relative_to(root).as_posix(),
                "byte_length": len(raw),
                "sha256": hashlib.sha256(raw).hexdigest(),
            }
        )
    return rows


def walk_keys(value: object) -> list[str]:
    keys: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            keys.append(key.lower())
            keys.extend(walk_keys(child))
    elif isinstance(value, list):
        for child in value:
            keys.extend(walk_keys(child))
    return keys


def main() -> int:
    if not ORIGINAL.is_dir():
        raise RuntimeError("original experiment directory missing")
    for directory in ("requests", "prompts", "raw", "normalized", "transcripts", "metadata"):
        (ROOT / directory).mkdir(parents=True, exist_ok=True)

    original_before = file_inventory(ORIGINAL)
    write_json(ROOT / "metadata/original-run-inventory-before.json", original_before)

    config_digest = digest_value(CONFIG)
    requests: list[dict[str, object]] = []
    leakage_checks: list[dict[str, object]] = []
    for challenge_id in EXPECTED_IDS:
        request = build_request(
            CHALLENGE_ROOT / f"{challenge_id}.json",
            evaluator_id="local-ollama-qwen2.5-3b-instruct",
            evaluator_version=f"ollama-{OLLAMA_VERSION}/model-{MODEL_ID}",
            config_digest=config_digest,
            execution_metadata={"invocation_id": f"qwen25-3b-post-wrapper-repair-{challenge_id}"},
        )
        validate_request(request)
        assert_oracle_blind_request(request)
        keys = walk_keys(request)
        forbidden_keys = sorted(set(keys) & BANNED_JSON_KEYS)
        request_bytes = canonical_json_bytes(request)
        prompt_bytes = make_prompt(request_bytes)
        prompt_text = prompt_bytes.decode("utf-8")
        forbidden_values = sorted(value for value in BANNED_VALUES if value in prompt_text)
        if forbidden_keys or forbidden_values or "oracle" in prompt_text.lower():
            raise RuntimeError(f"oracle leakage detected for {challenge_id}")
        (ROOT / f"requests/{challenge_id}.json").write_bytes(request_bytes)
        (ROOT / f"prompts/{challenge_id}.prompt.txt").write_bytes(prompt_bytes)
        requests.append(request)
        leakage_checks.append(
            {
                "challenge_id": challenge_id,
                "request_guard": "PASS",
                "forbidden_keys": forbidden_keys,
                "forbidden_values": forbidden_values,
            }
        )

    write_json(
        ROOT / "metadata/oracle-leakage-check.json",
        {
            "schema": "prf-oracle-leakage-check.v0",
            "status": "PASS",
            "requests_checked": len(requests),
            "answer_bearing_markers_found": 0,
            "checks": leakage_checks,
        },
    )

    wrapper = ROOT / "qwen_evaluator.py"
    summaries: list[dict[str, object]] = []
    for request in requests:
        challenge_id = request["challenge_id"]
        prompt_path = ROOT / f"prompts/{challenge_id}.prompt.txt"
        command = [sys.executable, str(wrapper), "--prompt-file", str(prompt_path)]
        started_at = now()
        transcript = run_command_adapter(
            request,
            command,
            timeout_seconds=300.0,
            recorded_at=started_at,
            invocation_metadata={
                "invocation_id": f"qwen25-3b-post-wrapper-repair-{challenge_id}",
                "provider": CONFIG["provider"],
                "model": MODEL,
                "model_id": MODEL_ID,
                "model_blob_digest": MODEL_BLOB_DIGEST,
                "ollama_version": OLLAMA_VERSION,
                "prompt_sha256": hashlib.sha256(prompt_path.read_bytes()).hexdigest(),
                "retry_policy": CONFIG["retry_policy"],
            },
        )
        ended_at = now()
        stdout_bytes = base64.b64decode(transcript["raw_response_base64"])
        stderr_bytes = base64.b64decode(transcript["stderr_base64"])
        (ROOT / f"raw/{challenge_id}.stdout.bin").write_bytes(stdout_bytes)
        (ROOT / f"raw/{challenge_id}.stderr.bin").write_bytes(stderr_bytes)
        if transcript["normalized_response"] is not None:
            write_json(ROOT / f"normalized/{challenge_id}.response.json", transcript["normalized_response"])
        write_json(ROOT / f"transcripts/{challenge_id}.transcript.json", transcript)
        summary = {
            "challenge_id": challenge_id,
            "request_sha256": digest_value(request),
            "prompt_sha256": hashlib.sha256(prompt_path.read_bytes()).hexdigest(),
            "raw_response_sha256": transcript["raw_response_digest"],
            "normalized_response_sha256": transcript["response_digest"],
            "evaluator_output_sha256": transcript["evaluator_output_digest"],
            "adapter_status": transcript["adapter_status"],
            "semantic_outcome": (
                transcript["evaluator_output"]["outcome"] if transcript["evaluator_output"] is not None else None
            ),
            "exit_code": transcript["exit_code"],
            "started_at": started_at,
            "ended_at": ended_at,
            "timestamp_authoritative": False,
        }
        write_json(ROOT / f"metadata/{challenge_id}.json", summary)
        summaries.append(summary)

    original_after = file_inventory(ORIGINAL)
    write_json(ROOT / "metadata/original-run-inventory-after.json", original_after)
    if original_before != original_after:
        raise RuntimeError("original experiment evidence changed during repaired run")

    write_json(
        ROOT / "capture-summary.json",
        {
            "schema": "prf-qwen25-3b-post-wrapper-repair-capture.v0",
            "capture_complete": len(summaries) == 6,
            "scoring_performed": False,
            "one_call_per_challenge": True,
            "no_retries": True,
            "no_conversation_memory": True,
            "model_calls": len(summaries),
            "configuration": CONFIG,
            "configuration_digest": config_digest,
            "original_experiment_unchanged": True,
            "results": summaries,
        },
    )
    print(json.dumps(summaries, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
