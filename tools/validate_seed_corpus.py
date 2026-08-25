from corpus_contract import (
    recompute_projection_claims,
    validate_all_cases_against_schema,
    validate_blind_challenge_views,
    validate_fixture_case_shape,
    validate_manifest_integrity,
    validate_oracle_coverage,
    validate_semantic_expectations,
    iter_case_paths,
    load_json,
)


def main() -> int:
    validate_manifest_integrity()
    validate_oracle_coverage()
    validate_all_cases_against_schema()
    for path in iter_case_paths():
        validate_fixture_case_shape(load_json(path), path=path)
    recompute_projection_claims()
    validate_semantic_expectations()
    validate_blind_challenge_views()
    print("seed corpus validation: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
