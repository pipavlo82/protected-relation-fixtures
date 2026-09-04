from __future__ import annotations

import argparse
import json
from pathlib import Path

if __package__:
    from .contract import AdapterContractViolation, run_command_adapter
else:
    from contract import AdapterContractViolation, run_command_adapter


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("request", type=Path)
    parser.add_argument("transcript", type=Path)
    parser.add_argument("--timeout", type=float, default=30.0)
    parser.add_argument("--adapter-command", nargs=argparse.REMAINDER, required=True)
    args = parser.parse_args()
    try:
        request = json.loads(args.request.read_text(encoding="utf-8"))
        transcript = run_command_adapter(
            request,
            args.adapter_command,
            timeout_seconds=args.timeout,
        )
    except (OSError, json.JSONDecodeError, AdapterContractViolation) as exc:
        print(f"adapter run: FAIL: {exc}")
        return 2
    args.transcript.write_text(
        json.dumps(transcript, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(f"adapter run: {transcript['adapter_status']}")
    return 0 if transcript["adapter_status"] == "RESPONSE_VALID" else 2


if __name__ == "__main__":
    raise SystemExit(main())
