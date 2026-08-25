from collections import Counter
import hashlib
import json
import re
from pathlib import Path, PurePosixPath
from typing import Any

from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError


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
OPTIONAL_PROTECTED_RELATION_FIELDS = {"normalization"}
EXPECTED_MANIFEST_KEYS = {
    "schema",
    "corpus_version",
    "byte_format_requirement",
    "fixture_schema",
    "cases",
    "oracle",
}


class ContractViolation(ValueError):
    """A fail-closed corpus contract violation."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ContractViolation(message)


def load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ContractViolation(f"invalid UTF-8 JSON at {path}: {exc}") from exc


def validate_exact_json_bytes(path: Path) -> Any:
    raw = path.read_bytes()
    require(bool(raw), f"empty JSON artifact: {path}")
    require(not raw.startswith(b"\xef\xbb\xbf"), f"UTF-8 BOM forbidden: {path}")
    require(b"\r" not in raw, f"CR/CRLF forbidden: {path}")
    require(b"\x00" not in raw, f"NUL forbidden: {path}")
    require(raw.endswith(b"\n"), f"missing final LF: {path}")
    require(not raw.endswith(b"\n\n"), f"more than one final LF: {path}")
    return load_json(path)


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def iter_case_paths(manifest_path: Path = MANIFEST) -> list[Path]:
    return sorted((manifest_path.parent / "cases").glob("prf-*.json"))


def validate_fixture_case_shape(case: dict[str, Any], *, path: Path | None = None) -> None:
    require(isinstance(case, dict), "fixture must be an object")
    require(case.get("schema") == "protected-relation-fixture.v0", "fixture schema mismatch")
    require(isinstance(case.get("fixture_id"), str) and bool(case["fixture_id"]), "invalid fixture_id")
    require(case.get("class") in ALLOWED_CLASSES, "unsupported fixture class")
    protected_relation = case.get("protected_relation")
    require(isinstance(protected_relation, dict), "protected_relation must be an object")
    require(
        REQUIRED_PROTECTED_RELATION_FIELDS.issubset(protected_relation.keys())
        and set(protected_relation.keys()).issubset(
            REQUIRED_PROTECTED_RELATION_FIELDS | OPTIONAL_PROTECTED_RELATION_FIELDS
        ),
        "protected_relation field set mismatch",
    )
    require("before" in case and "after" in case, "fixture requires before and after")
    projections = case.get("projections", [])
    require(isinstance(projections, list), "projections must be an array")
    projection_ids: list[str] = []
    for projection in projections:
        require(isinstance(projection, dict), "projection must be an object")
        require(
            set(projection.keys()).issubset({"id", "before", "after", "preserved"}),
            "projection contains an undeclared field",
        )
        require(isinstance(projection.get("id"), str) and bool(projection["id"]), "invalid projection id")
        require(
            isinstance(projection.get("preserved"), bool) or projection.get("preserved") == "unknown",
            "invalid projection preserved value",
        )
        projection_ids.append(projection["id"])
    require(len(projection_ids) == len(set(projection_ids)), "duplicate projection id")
    expected = case.get("expected")
    require(isinstance(expected, dict), "expected must be an object")
    require(expected.get("semantic_outcome") in SEMANTIC_OUTCOMES, "invalid semantic outcome")
    for field in ("projection_preserved", "protected_relation_preserved"):
        if field in expected:
            value = expected[field]
            require(isinstance(value, bool) or value == "unknown", f"invalid {field}")
    require(isinstance(expected.get("reason_class"), str) and bool(expected["reason_class"]), "invalid reason_class")
    require(isinstance(expected.get("fail_closed_required"), bool), "fail_closed_required must be boolean")
    if path is not None:
        require(path.stem == case["fixture_id"], f"fixture_id/filename mismatch for {path.name}")


def validate_case_against_schema(case: dict[str, Any], *, path: Path, schema_path: Path = SCHEMA_PATH) -> None:
    schema = validate_exact_json_bytes(schema_path)
    try:
        Draft202012Validator.check_schema(schema)
    except SchemaError as exc:
        raise ContractViolation(f"invalid fixture schema: {exc.message}") from exc
    errors = sorted(Draft202012Validator(schema).iter_errors(case), key=lambda error: list(error.path))
    if errors:
        error = errors[0]
        location = "/".join(str(part) for part in error.absolute_path) or "<root>"
        raise ContractViolation(f"schema validation failed for {path.name} at {location}: {error.message}")


def validate_all_cases_against_schema(
    manifest_path: Path = MANIFEST,
    schema_path: Path = SCHEMA_PATH,
) -> None:
    for path in iter_case_paths(manifest_path):
        case = validate_exact_json_bytes(path)
        validate_case_against_schema(case, path=path, schema_path=schema_path)


def validate_manifest_integrity(manifest_path: Path = MANIFEST) -> None:
    manifest = validate_exact_json_bytes(manifest_path)
    require(isinstance(manifest, dict), "manifest must be an object")
    require(set(manifest.keys()) == EXPECTED_MANIFEST_KEYS, "manifest field set mismatch")
    require(manifest.get("schema") == "protected-relation-corpus-manifest.v0", "manifest schema mismatch")
    require(manifest.get("corpus_version") == "v0", "manifest corpus_version mismatch")
    require(manifest.get("fixture_schema") == "spec/fixture-schema.v0.json", "fixture_schema mismatch")
    schema = validate_exact_json_bytes(SCHEMA_PATH)
    try:
        Draft202012Validator.check_schema(schema)
    except SchemaError as exc:
        raise ContractViolation(f"invalid fixture schema: {exc.message}") from exc
    byte_format = manifest.get("byte_format_requirement")
    require(isinstance(byte_format, dict), "missing byte_format_requirement")
    require(byte_format.get("encoding") == "utf-8", "manifest encoding must be utf-8")
    require(byte_format.get("json") == "yes", "manifest JSON requirement missing")
    require(byte_format.get("final_lf") is True, "manifest final_lf must be true")
    require(byte_format.get("canonical_json") is False, "v0 must not claim canonical JSON")

    rows = manifest.get("cases")
    require(isinstance(rows, list) and bool(rows), "manifest cases must be a non-empty array")
    declared_paths: list[str] = []
    for row in rows:
        require(isinstance(row, dict) and set(row.keys()) == {"path", "sha256"}, "invalid manifest case row")
        relative_path = row["path"]
        require(isinstance(relative_path, str), "invalid case path")
        manifest_case_path = PurePosixPath(relative_path)
        require(
            len(manifest_case_path.parts) == 2
            and manifest_case_path.parts[0] == "cases"
            and re.fullmatch(r"prf-[0-9]{3}\.json", manifest_case_path.name) is not None,
            "invalid case path",
        )
        require(
            isinstance(row["sha256"], str)
            and re.fullmatch(r"[0-9a-f]{64}", row["sha256"]) is not None,
            "invalid case SHA-256",
        )
        path = manifest_path.parent / relative_path
        require(path.exists(), f"missing case {relative_path}")
        validate_exact_json_bytes(path)
        require(sha256_file(path) == row["sha256"], f"digest mismatch for {relative_path}")
        case = load_json(path)
        require(Path(relative_path).stem == case.get("fixture_id"), f"manifest/case id mismatch for {relative_path}")
        declared_paths.append(relative_path)
    require(len(declared_paths) == len(set(declared_paths)), "duplicate manifest case path")
    actual_paths = [f"cases/{path.name}" for path in iter_case_paths(manifest_path)]
    require(declared_paths == actual_paths, "manifest/case universe or order mismatch")

    oracle = manifest.get("oracle")
    require(isinstance(oracle, dict) and set(oracle.keys()) == {"path", "sha256"}, "invalid oracle binding")
    require(oracle.get("path") == "oracle/expected-results.json", "invalid oracle path")
    require(
        isinstance(oracle.get("sha256"), str)
        and re.fullmatch(r"[0-9a-f]{64}", oracle["sha256"]) is not None,
        "invalid oracle SHA-256",
    )
    oracle_path = manifest_path.parent / oracle["path"]
    require(oracle_path.exists(), "missing oracle")
    validate_exact_json_bytes(oracle_path)
    require(sha256_file(oracle_path) == oracle["sha256"], "oracle digest mismatch")


def validate_oracle_coverage(manifest_path: Path = MANIFEST) -> None:
    manifest = load_json(manifest_path)
    oracle_path = manifest_path.parent / manifest["oracle"]["path"]
    oracle = validate_exact_json_bytes(oracle_path)
    require(oracle.get("schema") == "protected-relation-oracle.v0", "oracle schema mismatch")
    require(oracle.get("corpus_version") == manifest.get("corpus_version"), "oracle corpus_version mismatch")
    results = oracle.get("results")
    require(isinstance(results, dict), "oracle results must be an object")
    case_ids = {Path(row["path"]).stem for row in manifest["cases"]}
    oracle_ids = set(results.keys())
    require(case_ids == oracle_ids, f"oracle coverage mismatch: {case_ids ^ oracle_ids}")


def _projection_map(case: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {projection["id"]: projection for projection in case.get("projections", [])}


def recompute_projection_claims(manifest_path: Path = MANIFEST) -> None:
    for path in iter_case_paths(manifest_path):
        case = load_json(path)
        fixture_id = case["fixture_id"]
        projections = _projection_map(case)
        for projection in projections.values():
            if projection["preserved"] != "unknown":
                require(
                    projection["preserved"] is (projection.get("before") == projection.get("after")),
                    f"projection preservation mismatch for {fixture_id}/{projection['id']}",
                )
        if fixture_id == "prf-001":
            require(len(case["before"]["A"]) == projections["P1-local-degree-A"]["before"], "prf-001 before degree mismatch")
            require(len(case["after"]["A"]) == projections["P1-local-degree-A"]["after"], "prf-001 after degree mismatch")
            require(bool(case["before"]["A"]) == projections["P0-edge-existence-from-A"]["before"], "prf-001 before edge mismatch")
            require(bool(case["after"]["A"]) == projections["P0-edge-existence-from-A"]["after"], "prf-001 after edge mismatch")
        elif fixture_id == "prf-002":
            before_endpoints = [case["before"]["source"], case["before"]["target"]]
            after_endpoints = [case["after"]["source"], case["after"]["target"]]
            require(before_endpoints == projections["shape-same-endpoints"]["before"], "prf-002 before endpoints mismatch")
            require(after_endpoints == projections["shape-same-endpoints"]["after"], "prf-002 after endpoints mismatch")
        elif fixture_id == "prf-003":
            require(("status" in case["before"]) == projections["status-slot-present"]["before"], "prf-003 before status mismatch")
            require(("status" in case["after"]) == projections["status-slot-present"]["after"], "prf-003 after status mismatch")
            require(isinstance(case["after"], dict) == projections["parseability-downstream"]["after"], "prf-003 parseability mismatch")
        elif fixture_id == "prf-004":
            before_targets = sorted({row["target"] for row in case["before"]["links"]})
            after_targets = sorted({row["target"] for row in case["after"]["links"]})
            require(before_targets == projections["set-like-neighbor-membership"]["before"], "prf-004 before target mismatch")
            require(after_targets == projections["set-like-neighbor-membership"]["after"], "prf-004 after target mismatch")
        elif fixture_id == "prf-005":
            transforms = case["before"]["transforms"]
            step_results = case["after"]["step_results"]
            require([row["id"] for row in transforms] == ["T1", "T2"], "prf-005 transform order mismatch")
            require([row["id"] for row in step_results] == ["T1", "T2"], "prf-005 step-result order mismatch")
            require(transforms[0]["locally_admissible"] is projections["T1-local-admissibility"]["before"], "prf-005 T1 admissibility mismatch")
            require(transforms[1]["locally_admissible"] is projections["T2-local-admissibility"]["before"], "prf-005 T2 admissibility mismatch")
            require(step_results[0]["locally_admissible"] is projections["T1-local-admissibility"]["after"], "prf-005 T1 result mismatch")
            require(step_results[1]["locally_admissible"] is projections["T2-local-admissibility"]["after"], "prf-005 T2 result mismatch")
            require(case["after"]["composition"] == "T2(T1(S0))", "prf-005 composition mismatch")
        elif fixture_id == "prf-006":
            before_raw = [case["before"]["source"], case["before"]["relation"], case["before"]["target"]]
            after_raw = [case["after"]["source"], case["after"]["relation"], case["after"]["target"]]
            before_canonical = list(_normalize_relation(case, case["before"]))
            after_canonical = list(_normalize_relation(case, case["after"]))
            require(before_raw == projections["raw-relation-triple"]["before"], "prf-006 before raw mismatch")
            require(after_raw == projections["raw-relation-triple"]["after"], "prf-006 after raw mismatch")
            require(before_canonical == projections["canonical-relation-triple"]["before"], "prf-006 before canonical mismatch")
            require(after_canonical == projections["canonical-relation-triple"]["after"], "prf-006 after canonical mismatch")
        else:
            raise ContractViolation(f"no projection recomputer for fixture {fixture_id}")


def _result(
    *,
    outcome: str,
    projection_preserved: bool,
    relation_preserved: bool | str,
    reason: str,
    fail_closed: bool,
) -> dict[str, Any]:
    return {
        "semantic_outcome": outcome,
        "projection_preserved": projection_preserved,
        "protected_relation_preserved": relation_preserved,
        "reason_class": reason,
        "fail_closed_required": fail_closed,
    }


def _normalize_relation(case: dict[str, Any], state: dict[str, Any]) -> tuple[str, str, str]:
    normalization = case["protected_relation"].get("normalization")
    require(isinstance(normalization, dict), f"missing normalization rules for {case['fixture_id']}")
    identity_aliases = normalization.get("identity_aliases")
    relation_aliases = normalization.get("relation_aliases")
    require(isinstance(identity_aliases, dict), "identity_aliases must be an object")
    require(isinstance(relation_aliases, dict), "relation_aliases must be an object")
    source = state.get("source")
    target = state.get("target")
    relation = state.get("relation")
    require(source in identity_aliases, f"undeclared source alias: {source}")
    require(target in identity_aliases, f"undeclared target alias: {target}")
    require(relation in relation_aliases, f"undeclared relation alias: {relation}")
    return identity_aliases[source], relation_aliases[relation], identity_aliases[target]


def derive_semantic_result(case: dict[str, Any]) -> dict[str, Any]:
    fixture_id = case["fixture_id"]
    projection_preserved = all(
        projection["preserved"] is True for projection in case.get("projections", [])
    )
    if fixture_id == "prf-001":
        preserved = set(case["before"]["A"]) == set(case["after"]["A"])
        return _result(
            outcome="PRESERVED" if preserved else "VIOLATED",
            projection_preserved=projection_preserved,
            relation_preserved=preserved,
            reason="exact-neighborhood-identity-preserved" if preserved else "same-degree-different-neighborhood-identity",
            fail_closed=not preserved,
        )
    if fixture_id == "prf-002":
        fields = ("source", "target", "relation")
        preserved = tuple(case["before"][field] for field in fields) == tuple(case["after"][field] for field in fields)
        return _result(
            outcome="PRESERVED" if preserved else "VIOLATED",
            projection_preserved=projection_preserved,
            relation_preserved=preserved,
            reason="exact-typed-relation-preserved" if preserved else "same-shape-different-relation-type",
            fail_closed=not preserved,
        )
    if fixture_id == "prf-003":
        vocabulary_preserved = case["after"].get("reason_vocabulary_preserved") is True
        exact_status = case["before"].get("status") == case["after"].get("status")
        if exact_status and vocabulary_preserved and case["before"].get("reason") == case["after"].get("reason"):
            return _result(
                outcome="PRESERVED",
                projection_preserved=projection_preserved,
                relation_preserved=True,
                reason="status-and-reason-preserved",
                fail_closed=False,
            )
        return _result(
            outcome="UNVERIFIABLE",
            projection_preserved=projection_preserved,
            relation_preserved="unknown",
            reason="version-skew-vocabulary-loss",
            fail_closed=True,
        )
    if fixture_id == "prf-004":
        def key(row: dict[str, Any]) -> tuple[str, str, str]:
            return row["source"], row["target"], row["relation"]

        preserved = Counter(map(key, case["before"]["links"])) == Counter(map(key, case["after"]["links"]))
        return _result(
            outcome="PRESERVED" if preserved else "VIOLATED",
            projection_preserved=projection_preserved,
            relation_preserved=preserved,
            reason="multiplicity-preserved" if preserved else "multiplicity-collapse",
            fail_closed=not preserved,
        )
    if fixture_id == "prf-005":
        predicate = case["before"]["protected_predicate"]
        field = predicate["path"]
        required_value = predicate["equals"]
        require(case["before"]["state"].get(field) == required_value, "prf-005 baseline violates its protected predicate")
        preserved = case["after"]["state"].get(field) == required_value
        return _result(
            outcome="PRESERVED" if preserved else "VIOLATED",
            projection_preserved=projection_preserved,
            relation_preserved=preserved,
            reason="composition-safe" if preserved else "pass-pass-compose-fail",
            fail_closed=not preserved,
        )
    if fixture_id == "prf-006":
        preserved = _normalize_relation(case, case["before"]) == _normalize_relation(case, case["after"])
        return _result(
            outcome="PRESERVED" if preserved else "VIOLATED",
            projection_preserved=projection_preserved,
            relation_preserved=preserved,
            reason="canonical-alias-normalization-preserves-relation" if preserved else "canonical-relation-drift",
            fail_closed=not preserved,
        )
    raise ContractViolation(f"no semantic recomputer for fixture {fixture_id}")


def validate_semantic_expectations(manifest_path: Path = MANIFEST) -> None:
    manifest = load_json(manifest_path)
    oracle_path = manifest_path.parent / manifest["oracle"]["path"]
    oracle = load_json(oracle_path)
    for path in iter_case_paths(manifest_path):
        case = load_json(path)
        fixture_id = case["fixture_id"]
        derived = derive_semantic_result(case)
        require(derived == case["expected"], f"derived/case.expected mismatch for {fixture_id}")
        require(derived == oracle["results"][fixture_id], f"derived/oracle mismatch for {fixture_id}")


def derive_challenge(case: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema": "protected-relation-challenge.v0",
        "fixture_id": case["fixture_id"],
        "class": case["class"],
        "protected_relation": case["protected_relation"],
        "before": case["before"],
        "after": case["after"],
    }


def validate_blind_challenge_views(manifest_path: Path = MANIFEST) -> None:
    challenge_root = manifest_path.parent / "challenge" / "cases"
    expected_names = {path.name for path in iter_case_paths(manifest_path)}
    actual_names = {path.name for path in challenge_root.glob("prf-*.json")}
    require(expected_names == actual_names, "challenge/case universe mismatch")
    for path in iter_case_paths(manifest_path):
        challenge_path = challenge_root / path.name
        challenge = validate_exact_json_bytes(challenge_path)
        full_case = load_json(path)
        require(challenge == derive_challenge(full_case), f"challenge drift for {path.name}")
        for banned_field in ("expected", "metadata", "projections"):
            require(
                not _contains_key(challenge, banned_field),
                f"answer-bearing field {banned_field} in {path.name}",
            )


def _contains_key(value: Any, target: str) -> bool:
    if isinstance(value, dict):
        return target in value or any(_contains_key(child, target) for child in value.values())
    if isinstance(value, list):
        return any(_contains_key(child, target) for child in value)
    return False
