import hashlib
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "corpus" / "v0" / "manifest.json"
SCHEMA_PATH = ROOT / "spec" / "fixture-schema.v0.json"

ALLOWED_CLASSES = {
    "projection-equivalent-relation-non-equivalent",
    "raw-different-relation-equivalent",
    "composition-sensitive",
    "unknown-state-preservation",
}
SEMANTIC_OUTCOMES = {"PRESERVED", "VIOLATED", "UNVERIFIABLE"}
REQUIRED_PROTECTED_RELATION_FIELDS = {
    "kind",
    "identity_policy",
    "relation_type_policy",
    "multiplicity_policy",
    "direction_policy",
    "scope",
    "universe",
    "equivalence_policy",
    "policy_version",
}


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def iter_case_paths() -> list[Path]:
    return sorted((MANIFEST.parent / "cases").glob("prf-*.json"))


def validate_fixture_case_shape(case: dict[str, Any], *, path: Path | None = None) -> None:
    assert case["schema"] == "protected-relation-fixture.v0"
    assert isinstance(case["fixture_id"], str) and case["fixture_id"]
    assert case["class"] in ALLOWED_CLASSES
    pr = case["protected_relation"]
    assert isinstance(pr, dict)
    assert REQUIRED_PROTECTED_RELATION_FIELDS == set(pr.keys())
    assert isinstance(case["before"], (dict, list, str, int, float, bool)) or case["before"] is None
    assert isinstance(case["after"], (dict, list, str, int, float, bool)) or case["after"] is None
    projections = case.get("projections", [])
    assert isinstance(projections, list)
    for proj in projections:
        assert set(proj.keys()).issubset({"id", "before", "after", "preserved"})
        assert isinstance(proj["id"], str) and proj["id"]
        assert isinstance(proj["preserved"], bool) or proj["preserved"] == "unknown"
    expected = case["expected"]
    assert expected["semantic_outcome"] in SEMANTIC_OUTCOMES
    if "projection_preserved" in expected:
        assert isinstance(expected["projection_preserved"], bool) or expected["projection_preserved"] == "unknown"
    if "protected_relation_preserved" in expected:
        assert isinstance(expected["protected_relation_preserved"], bool) or expected["protected_relation_preserved"] == "unknown"
    if path is not None:
        assert path.stem == case["fixture_id"], f"fixture_id/filename mismatch for {path.name}"


def validate_manifest_integrity() -> None:
    manifest = load_json(MANIFEST)
    assert manifest["schema"] == "protected-relation-corpus-manifest.v0"
    assert manifest["corpus_version"] == "v0"
    assert "byte_format_requirement" in manifest
    cases = manifest["cases"]
    for row in cases:
        path = MANIFEST.parent / row["path"]
        assert path.exists(), f"missing case {row['path']}"
        assert sha256_file(path) == row["sha256"], f"digest mismatch for {row['path']}"
        case = load_json(path)
        assert Path(row["path"]).stem == case["fixture_id"], f"manifest/case id mismatch for {row['path']}"
    oracle = manifest["oracle"]
    oracle_path = MANIFEST.parent / oracle["path"]
    assert oracle_path.exists(), "missing oracle"
    assert sha256_file(oracle_path) == oracle["sha256"], "oracle digest mismatch"


def validate_oracle_coverage() -> None:
    manifest = load_json(MANIFEST)
    oracle_path = MANIFEST.parent / manifest["oracle"]["path"]
    oracle = load_json(oracle_path)
    case_ids = {Path(row["path"]).stem for row in manifest["cases"]}
    oracle_ids = set(oracle["results"].keys())
    assert case_ids == oracle_ids, f"oracle coverage mismatch: {case_ids ^ oracle_ids}"


def recompute_projection_claims() -> None:
    for path in iter_case_paths():
        case = load_json(path)
        fid = case["fixture_id"]
        projections = {p["id"]: p for p in case.get("projections", [])}
        if fid == "prf-001":
            assert len(case["before"]["A"]) == projections["P1-local-degree-A"]["before"]
            assert len(case["after"]["A"]) == projections["P1-local-degree-A"]["after"]
            assert (len(case["before"]["A"]) > 0) == projections["P0-edge-existence-from-A"]["before"]
            assert (len(case["after"]["A"]) > 0) == projections["P0-edge-existence-from-A"]["after"]
        elif fid == "prf-002":
            assert (case["before"]["source"], case["before"]["target"]) == tuple(projections["shape-same-endpoints"]["before"])
            assert (case["after"]["source"], case["after"]["target"]) == tuple(projections["shape-same-endpoints"]["after"])
            assert (case["before"]["source"] == "A" and case["before"]["target"] == "B") == projections["P0-edge-exists-A-B"]["before"]
            assert (case["after"]["source"] == "A" and case["after"]["target"] == "B") == projections["P0-edge-exists-A-B"]["after"]
        elif fid == "prf-003":
            assert isinstance(case["before"], dict) and isinstance(case["after"], dict)
            assert ("status" in case["before"]) == projections["status-slot-present"]["before"]
            assert ("status" in case["after"]) == projections["status-slot-present"]["after"]
            assert isinstance(case["after"], dict) == projections["parseability-downstream"]["after"]
        elif fid == "prf-004":
            before_targets = sorted({row["target"] for row in case["before"]["links"]})
            after_targets = sorted({row["target"] for row in case["after"]["links"]})
            assert before_targets == projections["set-like-neighbor-membership"]["before"]
            assert after_targets == projections["set-like-neighbor-membership"]["after"]
            assert ("A", "B") in {(row["source"], row["target"]) for row in case["before"]["links"]}
            assert projections["edge-exists-A-B"]["before"] is True
            assert ("A", "B") in {(row["source"], row["target"]) for row in case["after"]["links"]}
            assert projections["edge-exists-A-B"]["after"] is True
        elif fid == "prf-005":
            assert case["before"]["transforms"] == ["T1", "T2"]
            assert case["after"]["composition"] == "T2(T1(S0))"
            assert projections["T1-local-admissibility"]["after"] is True
            assert projections["T2-local-admissibility"]["after"] is True
        else:
            raise AssertionError(f"unexpected fixture id {fid}")


def derive_challenge(case: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema": "protected-relation-challenge.v0",
        "fixture_id": case["fixture_id"],
        "class": case["class"],
        "protected_relation": case["protected_relation"],
        "before": case["before"],
        "after": case["after"],
    }


def validate_blind_challenge_views() -> None:
    challenge_root = MANIFEST.parent / "challenge" / "cases"
    for path in iter_case_paths():
        challenge_path = challenge_root / path.name
        assert challenge_path.exists(), f"missing challenge view {path.name}"
        full_case = load_json(path)
        challenge = load_json(challenge_path)
        assert challenge == derive_challenge(full_case), f"challenge drift for {path.name}"
        assert "expected" not in challenge
        assert "metadata" not in challenge
        assert "projections" not in challenge
