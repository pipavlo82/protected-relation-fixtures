from corpus_contract import validate_manifest_integrity


def main() -> int:
    validate_manifest_integrity()
    print("manifest validation: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
