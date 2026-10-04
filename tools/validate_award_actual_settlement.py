from __future__ import annotations

import json

try:
    from tools.award_actual_settlement import ProfileError, validate_suite
except ModuleNotFoundError:
    from award_actual_settlement import ProfileError, validate_suite


def main() -> int:
    try:
        report = validate_suite()
    except (ProfileError, OSError) as exc:
        print(f"AWARD_ACTUAL_SETTLEMENT_FAIL: {exc}")
        return 1
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
