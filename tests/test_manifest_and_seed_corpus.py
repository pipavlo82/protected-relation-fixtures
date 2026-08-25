import copy
import json
from pathlib import Path
import shutil
import tempfile
import unittest

from tools.corpus_contract import (
    ContractViolation,
    MANIFEST,
    SCHEMA_PATH,
    iter_case_paths,
    load_json,
    recompute_projection_claims,
    validate_all_cases_against_schema,
    validate_blind_challenge_views,
    validate_case_against_schema,
    validate_exact_json_bytes,
    validate_fixture_case_shape,
    validate_manifest_integrity,
    validate_oracle_coverage,
    validate_semantic_expectations,
)


class CorpusContractTests(unittest.TestCase):
    def _copy_corpus(self, destination: Path) -> Path:
        target = destination / "v0"
        shutil.copytree(MANIFEST.parent, target)
        return target / "manifest.json"

    def test_manifest_integrity(self) -> None:
        validate_manifest_integrity()

    def test_all_cases_validate_against_seed_contract(self) -> None:
        for path in iter_case_paths():
            validate_fixture_case_shape(load_json(path), path=path)

    def test_all_cases_validate_against_json_schema(self) -> None:
        validate_all_cases_against_schema()

    def test_seed_oracle_covers_all_cases(self) -> None:
        validate_oracle_coverage()

    def test_seed_projection_claims_recompute(self) -> None:
        recompute_projection_claims()

    def test_seed_semantic_outcomes_recompute_and_match_oracle(self) -> None:
        validate_semantic_expectations()

    def test_blind_challenge_views_are_detached(self) -> None:
        validate_blind_challenge_views()

    def test_manifest_digest_mutation_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            manifest_path = self._copy_corpus(Path(directory))
            oracle_path = manifest_path.parent / "oracle" / "expected-results.json"
            raw = oracle_path.read_bytes()
            oracle_path.write_bytes(raw.replace(b"PRESERVED", b"VIOLATED", 1))
            with self.assertRaisesRegex(ContractViolation, "oracle digest mismatch"):
                validate_manifest_integrity(manifest_path)

    def test_manifest_path_traversal_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            manifest_path = self._copy_corpus(Path(directory))
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["cases"][0]["path"] = "cases/prf-../oracle/expected-results.json"
            manifest_path.write_text(
                json.dumps(manifest, indent=2) + "\n",
                encoding="utf-8",
                newline="\n",
            )
            with self.assertRaisesRegex(ContractViolation, "invalid case path"):
                validate_manifest_integrity(manifest_path)

    def test_byte_format_mutations_are_rejected(self) -> None:
        variants = {
            "bom": b"\xef\xbb\xbf{}\n",
            "crlf": b"{}\r\n",
            "nul": b'{"x":"\\u0000"}\x00\n',
            "missing-final-lf": b"{}",
            "extra-final-lf": b"{}\n\n",
        }
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name, raw in variants.items():
                path = root / f"{name}.json"
                path.write_bytes(raw)
                with self.subTest(name=name), self.assertRaises(ContractViolation):
                    validate_exact_json_bytes(path)

    def test_schema_rejects_an_undeclared_top_level_field(self) -> None:
        path = iter_case_paths()[0]
        case = copy.deepcopy(load_json(path))
        case["undeclared"] = True
        with self.assertRaisesRegex(ContractViolation, "schema validation failed"):
            validate_case_against_schema(case, path=path, schema_path=SCHEMA_PATH)

    def test_oracle_semantic_mutation_is_rejected_even_when_parseable(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            manifest_path = self._copy_corpus(Path(directory))
            oracle_path = manifest_path.parent / "oracle" / "expected-results.json"
            oracle = json.loads(oracle_path.read_text(encoding="utf-8"))
            oracle["results"]["prf-001"]["semantic_outcome"] = "PRESERVED"
            oracle_path.write_text(json.dumps(oracle, indent=2) + "\n", encoding="utf-8", newline="\n")
            with self.assertRaisesRegex(ContractViolation, "derived/oracle mismatch for prf-001"):
                validate_semantic_expectations(manifest_path)

    def test_composition_fixture_is_load_bearing(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            manifest_path = self._copy_corpus(Path(directory))
            case_path = manifest_path.parent / "cases" / "prf-005.json"
            case = json.loads(case_path.read_text(encoding="utf-8"))
            case["after"]["state"]["authorization_scope"] = "agent-A-only"
            case_path.write_text(json.dumps(case, indent=2) + "\n", encoding="utf-8", newline="\n")
            with self.assertRaisesRegex(ContractViolation, "derived/case.expected mismatch for prf-005"):
                validate_semantic_expectations(manifest_path)

    def test_mirror_positive_normalization_is_load_bearing(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            manifest_path = self._copy_corpus(Path(directory))
            case_path = manifest_path.parent / "cases" / "prf-006.json"
            case = json.loads(case_path.read_text(encoding="utf-8"))
            case["after"]["source"] = "undeclared:alice"
            case_path.write_text(json.dumps(case, indent=2) + "\n", encoding="utf-8", newline="\n")
            with self.assertRaisesRegex(ContractViolation, "undeclared source alias"):
                validate_semantic_expectations(manifest_path)


if __name__ == "__main__":
    unittest.main()
