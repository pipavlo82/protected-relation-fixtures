import json

from corpus_contract import MANIFEST, derive_challenge, iter_case_paths, validate_exact_json_bytes


CHALLENGE = MANIFEST.parent / "challenge" / "cases"


def main() -> int:
    for path in iter_case_paths():
        case = validate_exact_json_bytes(path)
        challenge = derive_challenge(case)
        out = CHALLENGE / path.name
        text = json.dumps(challenge, ensure_ascii=False, indent=2) + "\n"
        out.write_text(text, encoding="utf-8", newline="\n")
    print("challenge derivation: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
