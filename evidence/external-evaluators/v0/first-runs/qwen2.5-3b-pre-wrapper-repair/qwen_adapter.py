from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys


REPO = Path(
    r"C:\Users\msi\Documents\Codex\2026-08-25\we-are-closing-the-erc-8309"
    r"\protected-relation-fixtures"
)
sys.path.insert(0, str(REPO))

from adapters.v0.contract import canonical_json_bytes, validate_request  # noqa: E402


FIXED_INSTRUCTION = """You are an external Protected Relation Fixtures semantic evaluator.

Apply ONLY the protected relation profile supplied by the request to the supplied before/after state.

Do not guess benchmark correctness and do not invent a different protected relation.

Return PRESERVED only if preservation is justified under the supplied relation.
Return VIOLATED only if violation is justified.
If the available semantic information is insufficient, return UNVERIFIABLE.

Return only a JSON object conforming to the supplied external-adapter response contract.
Copy challenge_id, challenge_digest, protected_relation_profile_digest, and the complete evaluator object exactly from the request.
Use schema value protected-relation-external-adapter-response.v0.
Use an uppercase reason_code, a string or null reason_detail, and an evidence array.
Do not add markdown fences, commentary, or fields not permitted by the response schema.
"""


def make_prompt(request: dict[str, object]) -> bytes:
    validate_request(request)
    request_bytes = canonical_json_bytes(request)
    response_schema = (REPO / "adapters/v0/response-schema.json").read_bytes()
    return (
        FIXED_INSTRUCTION.encode("utf-8")
        + b"\nEXACT VALIDATED BLIND REQUEST JSON:\n"
        + request_bytes
        + b"\n\nEXACT EXTERNAL-ADAPTER RESPONSE JSON SCHEMA:\n"
        + response_schema
    )


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def write_json(path: Path, value: object) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--experiment-root", type=Path, required=True)
    args = parser.parse_args()
    request = validate_request(json.loads(sys.stdin.buffer.read().decode("utf-8")))
    challenge_id = request["challenge_id"]
    prompt = make_prompt(request)
    prompt_path = args.experiment_root / "prompts" / f"{challenge_id}.prompt.txt"
    prompt_path.write_bytes(prompt)

    command = [
        "wsl.exe",
        "-d",
        "Ubuntu",
        "--",
        "env",
        "OLLAMA_NOHISTORY=1",
        "/usr/local/bin/ollama",
        "run",
        "qwen2.5:3b-instruct",
        "--format",
        "json",
        "--hidethinking",
        "--keepalive",
        "0",
    ]
    started_at = utc_now()
    timed_out = False
    try:
        process = subprocess.run(
            command,
            input=prompt,
            capture_output=True,
            check=False,
            timeout=300,
            env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
        )
        stdout = process.stdout
        stderr = process.stderr
        returncode = process.returncode
    except subprocess.TimeoutExpired as exc:
        stdout = exc.stdout or b""
        stderr = exc.stderr or b""
        returncode = 124
        timed_out = True
    ended_at = utc_now()

    raw_path = args.experiment_root / "raw" / f"{challenge_id}.stdout.bin"
    stderr_path = args.experiment_root / "raw" / f"{challenge_id}.stderr.bin"
    raw_path.write_bytes(stdout)
    stderr_path.write_bytes(stderr)
    write_json(
        args.experiment_root / "metadata" / f"{challenge_id}.invocation.json",
        {
            "schema": "prf-local-ollama-invocation.v0",
            "challenge_id": challenge_id,
            "command": command,
            "model": "qwen2.5:3b-instruct",
            "ollama_version": "0.15.2",
            "model_id": "357c53fb659c",
            "model_blob_digest": "sha256:5ee4f07cdb9beadbbb293e85803c569b01bd37ed059d2715faa7bb405f31caa6",
            "prompt_sha256": hashlib.sha256(prompt).hexdigest(),
            "raw_stdout_sha256": hashlib.sha256(stdout).hexdigest(),
            "raw_stderr_sha256": hashlib.sha256(stderr).hexdigest(),
            "started_at": started_at,
            "ended_at": ended_at,
            "timestamps_authoritative": False,
            "timeout_seconds": 300,
            "timed_out": timed_out,
            "exit_code": returncode,
        },
    )
    sys.stdout.buffer.write(stdout)
    sys.stdout.buffer.flush()
    sys.stderr.buffer.write(stderr)
    sys.stderr.buffer.flush()
    return returncode


if __name__ == "__main__":
    raise SystemExit(main())
