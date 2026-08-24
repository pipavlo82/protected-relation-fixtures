import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CASES = ROOT / "corpus" / "v0" / "cases"
CHALLENGE = ROOT / "corpus" / "v0" / "challenge" / "cases"


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def derive_challenge(case: dict) -> dict:
    return {
        "schema": "protected-relation-challenge.v0",
        "fixture_id": case["fixture_id"],
        "class": case["class"],
        "protected_relation": case["protected_relation"],
        "before": case["before"],
        "after": case["after"],
    }


def main() -> int:
    for path in sorted(CASES.glob("prf-*.json")):
        case = load_json(path)
        challenge = derive_challenge(case)
        out = CHALLENGE / path.name
        text = json.dumps(challenge, ensure_ascii=False, indent=2) + "\n"
        out.write_text(text, encoding="utf-8", newline="\n")
    print("challenge derivation: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
