from __future__ import annotations

import argparse
import os
from pathlib import Path
import subprocess
import sys


MODEL = "qwen2.5-coder:7b"
INSTRUCTION = """You are an external Protected Relation Fixtures semantic evaluator.

Apply ONLY the protected relation profile supplied by the request to the supplied before/after state.

Do not guess benchmark correctness and do not invent a different protected relation.

Return PRESERVED only if preservation is justified under the supplied relation.
Return VIOLATED only if violation is justified.
If the available semantic information is insufficient, return UNVERIFIABLE.

Return only one JSON object with exactly these two fields and no others:
{"outcome":"PRESERVED | VIOLATED | UNVERIFIABLE","reason_detail":"string"}

The outcome value must be exactly one of PRESERVED, VIOLATED, or UNVERIFIABLE. The reason_detail value must be a JSON string.

Validated blind request:
"""


def make_prompt(request_json_bytes: bytes) -> bytes:
    return INSTRUCTION.encode("utf-8") + request_json_bytes + b"\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--prompt-file", type=Path, required=True)
    args = parser.parse_args()

    wire = sys.stdin.buffer.read()
    if not wire.endswith(b"\n") or wire.endswith(b"\n\n") or b"\r" in wire:
        print("invalid request framing", file=sys.stderr)
        return 64
    request_json_bytes = wire[:-1]
    prompt = make_prompt(request_json_bytes)
    if not args.prompt_file.is_file() or args.prompt_file.read_bytes() != prompt:
        print("prompt bytes do not match frozen prompt file", file=sys.stderr)
        return 65

    command = [
        "wsl.exe",
        "-d",
        "Ubuntu",
        "--",
        "env",
        "OLLAMA_NOHISTORY=1",
        "/usr/local/bin/ollama",
        "run",
        MODEL,
        "--format",
        "json",
        "--hidethinking",
        "--keepalive",
        "0",
        prompt.decode("utf-8"),
    ]
    environment = os.environ.copy()
    environment["OLLAMA_NOHISTORY"] = "1"
    process = subprocess.run(command, capture_output=True, check=False, env=environment)
    sys.stdout.buffer.write(process.stdout)
    sys.stdout.buffer.flush()
    sys.stderr.buffer.write(process.stderr)
    sys.stderr.buffer.flush()
    return process.returncode


if __name__ == "__main__":
    raise SystemExit(main())
