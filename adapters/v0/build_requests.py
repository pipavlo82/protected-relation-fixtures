from __future__ import annotations

import argparse
import json
from pathlib import Path

if __package__:
    from .contract import CHALLENGE_ROOT, build_request
else:
    from contract import CHALLENGE_ROOT, build_request


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--evaluator-id", required=True)
    parser.add_argument("--evaluator-version", required=True)
    parser.add_argument("--config-digest", required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    for challenge_path in sorted(CHALLENGE_ROOT.glob("prf-*.json")):
        request = build_request(
            challenge_path,
            evaluator_id=args.evaluator_id,
            evaluator_version=args.evaluator_version,
            config_digest=args.config_digest,
        )
        output = args.output_dir / challenge_path.name
        output.write_text(json.dumps(request, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
        print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
