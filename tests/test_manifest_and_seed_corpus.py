import unittest

from tools.corpus_contract import (
    validate_blind_challenge_views,
    validate_fixture_case_shape,
    validate_manifest_integrity,
    validate_oracle_coverage,
    recompute_projection_claims,
    iter_case_paths,
    load_json,
)


class CorpusContractTests(unittest.TestCase):
    def test_manifest_integrity(self) -> None:
        validate_manifest_integrity()

    def test_all_cases_validate_against_seed_contract(self) -> None:
        for path in iter_case_paths():
            validate_fixture_case_shape(load_json(path), path=path)

    def test_seed_oracle_covers_all_cases(self) -> None:
        validate_oracle_coverage()

    def test_seed_projection_claims_recompute(self) -> None:
        recompute_projection_claims()

    def test_blind_challenge_views_are_detached(self) -> None:
        validate_blind_challenge_views()


if __name__ == "__main__":
    unittest.main()
