from corpus_contract import validate_manifest_integrity, validate_oracle_coverage


def main() -> int:
    validate_manifest_integrity()
    validate_oracle_coverage()
    print("manifest validation: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
