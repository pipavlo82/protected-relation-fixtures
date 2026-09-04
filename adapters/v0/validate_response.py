from __future__ import annotations

import argparse
import json
from pathlib import Path

if __package__:
    from .contract import AdapterContractViolation, validate_response
else:
    from contract import AdapterContractViolation, validate_response


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("request", type=Path)
    parser.add_argument("response", type=Path)
    args = parser.parse_args()
    try:
        request = json.loads(args.request.read_text(encoding="utf-8"))
        response = json.loads(args.response.read_text(encoding="utf-8"))
        validate_response(request, response)
    except (OSError, json.JSONDecodeError, AdapterContractViolation) as exc:
        print(f"adapter response validation: FAIL: {exc}")
        return 1
    print("adapter response validation: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
