from __future__ import annotations

from datetime import datetime, timezone
import base64
import hashlib
import json
import os
from pathlib import Path
import sys


REPO = Path(
    r"C:\Users\msi\Documents\Codex\2026-08-25\we-are-closing-the-erc-8309"
    r"\protected-relation-fixtures"
)
ROOT = Path(r"D:\prf-experiments\qwen2.5-3b-instruct-first-run")
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
from qwen_adapter import make_prompt  # noqa: E402


MODEL = "qwen2.5:3b-instruct"
MODEL_ID = "357c53fb659c"
MODEL_BLOB_DIGEST = "sha256:5ee4f07cdb9beadbbb293e85803c569b01bd37ed059d2715faa7bb405f31caa6"
OLLAMA_VERSION = "0.15.2"
EXPECTED_IDS = [f"prf-{index:03d}" for index in range(1, 7)]
BANNED_PROMPT_MARKERS = (
    "oracle",
    "expected outcome",
    "expected_outcome",
    "benchmark classification",
    "mismatch_classification",
    "reference evaluator",
)


def write_json(path: Path, value: object) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def main() -> int:
    if any((ROOT / "raw").glob("prf-*.stdout.bin")):
        raise RuntimeError("first-run raw outputs already exist; refusing a second call")

    config = {
        "provider": "local-ollama-wsl",
        "wsl_distro": "Ubuntu",
        "ollama_executable": "/usr/local/bin/ollama",
        "ollama_version": OLLAMA_VERSION,
        "model": MODEL,
        "model_id": MODEL_ID,
        "model_blob_digest": MODEL_BLOB_DIGEST,
        "response_format": "json",
        "hide_thinking": True,
        "keepalive": "0",
        "history": False,
        "model_calls_per_challenge": 1,
    }
    config_digest = digest_value(config)
    write_json(ROOT / "metadata" / "evaluator-config.json", config)

    requests: list[dict[str, object]] = []
    leak_rows: list[dict[str, object]] = []
    for challenge_path in sorted(CHALLENGE_ROOT.glob("prf-*.json")):
        request = build_request(
            challenge_path,
            evaluator_id="local-ollama/qwen2.5:3b-instruct",
            evaluator_version=f"ollama-{OLLAMA_VERSION}/model-{MODEL_ID}",
            config_digest=config_digest,
            execution_metadata={"invocation_id": f"qwen25-3b-first-run-{challenge_path.stem}"},
        )
        validate_request(request)
        assert_oracle_blind_request(request)
        request_bytes = canonical_json_bytes(request)
        prompt = make_prompt(request)
        prompt_text = prompt.decode("utf-8").lower()
        found = [marker for marker in BANNED_PROMPT_MARKERS if marker in prompt_text]
        leak_rows.append(
            {
                "challenge_id": request["challenge_id"],
                "request_guard": "PASS",
                "banned_prompt_markers_found": found,
            }
        )
        if found:
            write_json(ROOT / "metadata" / "oracle-leakage-check.json", leak_rows)
            raise RuntimeError(f"answer-bearing prompt marker detected for {request['challenge_id']}: {found}")
        (ROOT / "requests" / f"{request['challenge_id']}.request.json").write_bytes(request_bytes)
        requests.append(request)

    if [request["challenge_id"] for request in requests] != EXPECTED_IDS:
        raise RuntimeError("canonical six-request set mismatch")
    write_json(
        ROOT / "metadata" / "oracle-leakage-check.json",
        {
            "schema": "prf-oracle-leakage-check.v0",
            "status": "PASS",
            "requests_checked": 6,
            "answer_bearing_markers_found": 0,
            "checks": leak_rows,
        },
    )

    wrapper = ROOT / "qwen_adapter.py"
    transcript_rows: list[dict[str, object]] = []
    for request in requests:
        challenge_id = request["challenge_id"]
        transcript = run_command_adapter(
            request,
            [sys.executable, str(wrapper), "--experiment-root", str(ROOT)],
            timeout_seconds=360,
        )
        raw_from_transcript = base64.b64decode(transcript["raw_response_base64"])
        raw_path = ROOT / "raw" / f"{challenge_id}.stdout.bin"
        if raw_path.read_bytes() != raw_from_transcript:
            raise RuntimeError(f"raw stdout capture mismatch: {challenge_id}")
        write_json(ROOT / "transcripts" / f"{challenge_id}.transcript.json", transcript)
        normalized = transcript["normalized_response"]
        if normalized is not None:
            write_json(ROOT / "normalized" / f"{challenge_id}.response.json", normalized)
        request_bytes = (ROOT / "requests" / f"{challenge_id}.request.json").read_bytes()
        prompt_bytes = (ROOT / "prompts" / f"{challenge_id}.prompt.txt").read_bytes()
        transcript_rows.append(
            {
                "challenge_id": challenge_id,
                "request_sha256": hashlib.sha256(request_bytes).hexdigest(),
                "prompt_sha256": hashlib.sha256(prompt_bytes).hexdigest(),
                "raw_stdout_sha256": hashlib.sha256(raw_from_transcript).hexdigest(),
                "normalized_response_sha256": transcript["response_digest"],
                "adapter_status": transcript["adapter_status"],
                "semantic_outcome": normalized.get("outcome") if normalized else None,
                "transcript_path": str(ROOT / "transcripts" / f"{challenge_id}.transcript.json"),
            }
        )

    write_json(
        ROOT / "capture-summary.json",
        {
            "schema": "prf-qwen25-3b-first-run-capture.v0",
            "capture_complete": len(transcript_rows) == 6,
            "model_calls": len(transcript_rows),
            "one_call_per_challenge": True,
            "no_conversation_memory": True,
            "captured_at": datetime.now(timezone.utc).isoformat(),
            "timestamp_authoritative": False,
            "evaluator_config_digest": config_digest,
            "results": transcript_rows,
        },
    )
    print(json.dumps(transcript_rows, indent=2))
    return 0


if __name__ == "__main__":
    os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
    raise SystemExit(main())
