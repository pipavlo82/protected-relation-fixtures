from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[1]
SUITE_PATH = ROOT / "conformance" / "relation-discrimination-v0" / "suite.json"

OUTCOMES = {"PRESERVED", "VIOLATED", "UNVERIFIABLE"}
REQUIRED_AXES = (
    "identity",
    "relation_type",
    "multiplicity",
    "direction",
    "scope",
)
AXIS_POLICY_FIELDS = {
    "identity": ({"identity_policy"}, {"identity_policy", "identity_aliases"}),
    "relation_type": (
        {"relation_type_policy"},
        {"relation_type_policy", "relation_type_aliases"},
    ),
    "multiplicity": ({"multiplicity_policy"}, {"multiplicity_policy"}),
    "direction": ({"direction_policy"}, {"direction_policy"}),
    "scope": ({"scope_policy"}, {"scope_policy", "scope_anchor"}),
}
POLICY_FIELDS = {
    "kind",
    "identity_policy",
    "identity_aliases",
    "relation_type_policy",
    "relation_type_aliases",
    "multiplicity_policy",
    "direction_policy",
    "scope_policy",
    "scope_anchor",
}


class RelationDiscriminationError(ValueError):
    """A fail-closed relation-discrimination contract violation."""


class _UnverifiableInput(ValueError):
    """Internal signal that semantic extraction cannot be justified."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RelationDiscriminationError(message)


def load_suite(path: Path = SUITE_PATH) -> dict[str, Any]:
    raw = path.read_bytes()
    require(bool(raw), f"empty relation-discrimination suite: {path}")
    require(not raw.startswith(b"\xef\xbb\xbf"), f"UTF-8 BOM forbidden: {path}")
    require(b"\r" not in raw, f"CR/CRLF forbidden: {path}")
    require(raw.endswith(b"\n"), f"missing final LF: {path}")
    require(not raw.endswith(b"\n\n"), f"more than one final LF: {path}")
    try:
        value = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RelationDiscriminationError(f"invalid UTF-8 JSON at {path}: {exc}") from exc
    require(isinstance(value, dict), "relation-discrimination suite must be an object")
    return value


def _unverifiable(reason: str) -> dict[str, str]:
    return {"outcome": "UNVERIFIABLE", "reason": reason}


def _require_string(value: Any, reason: str) -> str:
    if not isinstance(value, str) or not value:
        raise _UnverifiableInput(reason)
    return value


def _normalize_identity(policy: dict[str, Any], value: Any) -> str:
    identity = _require_string(value, "invalid-identity")
    kind = policy.get("identity_policy")
    if kind == "anchored":
        return identity
    if kind == "alias-permitted":
        aliases = policy.get("identity_aliases")
        if not isinstance(aliases, dict):
            raise _UnverifiableInput("missing-identity-alias-map")
        canonical = aliases.get(identity)
        if not isinstance(canonical, str) or not canonical:
            raise _UnverifiableInput(f"undeclared-identity-alias:{identity}")
        return canonical
    raise _UnverifiableInput(f"unsupported-identity-policy:{kind}")


def _normalize_relation_type(policy: dict[str, Any], value: Any) -> str:
    relation_type = _require_string(value, "invalid-relation-type")
    kind = policy.get("relation_type_policy")
    if kind == "typed-exact":
        return relation_type
    if kind == "type-ignored":
        return "*"
    if kind == "type-normalized":
        aliases = policy.get("relation_type_aliases")
        if not isinstance(aliases, dict):
            raise _UnverifiableInput("missing-relation-type-alias-map")
        canonical = aliases.get(relation_type)
        if not isinstance(canonical, str) or not canonical:
            raise _UnverifiableInput(f"undeclared-relation-type:{relation_type}")
        return canonical
    raise _UnverifiableInput(f"unsupported-relation-type-policy:{kind}")


def extract_protected_semantics(
    policy: dict[str, Any], state: dict[str, Any]
) -> dict[str, Any]:
    """Apply Phi_R without consulting the v0 seed corpus or its oracle."""
    try:
        if not isinstance(policy, dict) or policy.get("kind") != "edge-relation":
            raise _UnverifiableInput(f"unsupported-policy-kind:{policy.get('kind') if isinstance(policy, dict) else None}")
        if set(policy) != POLICY_FIELDS:
            raise _UnverifiableInput("unsupported-policy-field-set")
        if not isinstance(state, dict) or set(state) != {"complete_scopes", "relations"}:
            raise _UnverifiableInput("invalid-state-field-set")

        complete_scopes = state.get("complete_scopes")
        relations = state.get("relations")
        if (
            not isinstance(complete_scopes, list)
            or not all(isinstance(scope, str) and scope for scope in complete_scopes)
            or len(complete_scopes) != len(set(complete_scopes))
            or not isinstance(relations, list)
        ):
            raise _UnverifiableInput("insufficient-semantic-information")

        scope_policy = policy.get("scope_policy")
        if scope_policy == "global":
            if "global" not in complete_scopes:
                raise _UnverifiableInput("incomplete-global-scope")
            selected_scope = None
        elif scope_policy == "local-bounded":
            selected_scope = policy.get("scope_anchor")
            if not isinstance(selected_scope, str) or not selected_scope:
                raise _UnverifiableInput("missing-local-scope-anchor")
            if selected_scope not in complete_scopes:
                raise _UnverifiableInput(f"incomplete-local-scope:{selected_scope}")
        else:
            raise _UnverifiableInput(f"unsupported-scope-policy:{scope_policy}")

        direction_policy = policy.get("direction_policy")
        if direction_policy not in {"directed-exact", "direction-ignored"}:
            raise _UnverifiableInput(f"unsupported-direction-policy:{direction_policy}")
        multiplicity_policy = policy.get("multiplicity_policy")
        if multiplicity_policy not in {"multiset-exact", "set-collapsed"}:
            raise _UnverifiableInput(f"unsupported-multiplicity-policy:{multiplicity_policy}")

        canonical_relations: list[tuple[str, str, str, str]] = []
        for relation in relations:
            if not isinstance(relation, dict) or set(relation) != {
                "source",
                "relation_type",
                "target",
                "scope",
            }:
                raise _UnverifiableInput("invalid-relation-record")
            relation_scope = _require_string(relation["scope"], "invalid-relation-scope")
            if selected_scope is not None and relation_scope != selected_scope:
                continue
            source = _normalize_identity(policy, relation["source"])
            target = _normalize_identity(policy, relation["target"])
            relation_type = _normalize_relation_type(policy, relation["relation_type"])
            if direction_policy == "direction-ignored" and target < source:
                source, target = target, source
            canonical_relations.append((relation_scope, source, relation_type, target))

        if multiplicity_policy == "set-collapsed":
            canonical_relations = list(set(canonical_relations))
        canonical_relations.sort()
        return {
            "status": "OK",
            "semantic_object": {
                "kind": "edge-relation",
                "relations": [list(relation) for relation in canonical_relations],
            },
        }
    except _UnverifiableInput as exc:
        return {"status": "UNVERIFIABLE", "reason": str(exc)}


def compare_protected_semantics(
    before: dict[str, Any], after: dict[str, Any]
) -> dict[str, str]:
    """Apply Compare_R to two extraction results."""
    if before.get("status") != "OK":
        return _unverifiable(f"before:{before.get('reason', 'unknown-extraction-failure')}")
    if after.get("status") != "OK":
        return _unverifiable(f"after:{after.get('reason', 'unknown-extraction-failure')}")
    if before.get("semantic_object") == after.get("semantic_object"):
        return {"outcome": "PRESERVED", "reason": "canonical-protected-semantics-equal"}
    return {"outcome": "VIOLATED", "reason": "canonical-protected-semantics-differ"}


def evaluate_relation(
    policy: dict[str, Any], before: dict[str, Any], after: dict[str, Any]
) -> dict[str, str]:
    before_semantics = extract_protected_semantics(policy, before)
    after_semantics = extract_protected_semantics(policy, after)
    return compare_protected_semantics(before_semantics, after_semantics)


def classify_outcome_mismatch(expected: str, actual: str) -> str:
    require(expected in OUTCOMES, f"unknown expected outcome: {expected}")
    require(actual in OUTCOMES, f"unknown evaluator outcome: {actual}")
    if expected == actual:
        return "MATCH"
    if expected == "VIOLATED" and actual == "PRESERVED":
        return "UNSAFE_FALSE_PRESERVATION"
    if expected == "UNVERIFIABLE" and actual == "PRESERVED":
        return "UNSAFE_UNVERIFIABLE_UPGRADE"
    if expected == "PRESERVED" and actual == "VIOLATED":
        return "FALSE_VIOLATION"
    if expected == "PRESERVED" and actual == "UNVERIFIABLE":
        return "PRESERVATION_NOT_ESTABLISHED"
    if expected == "VIOLATED" and actual == "UNVERIFIABLE":
        return "VIOLATION_NOT_ESTABLISHED"
    if expected == "UNVERIFIABLE" and actual == "VIOLATED":
        return "UNVERIFIABLE_MISCLASSIFIED_AS_VIOLATION"
    return "OUTCOME_MISMATCH"


def _policy_diff(left: dict[str, Any], right: dict[str, Any]) -> set[str]:
    return {
        key
        for key in set(left) | set(right)
        if left.get(key) != right.get(key)
    }


Evaluator = Callable[[dict[str, Any], dict[str, Any], dict[str, Any]], dict[str, str]]


def validate_relation_discrimination(
    suite: dict[str, Any], *, evaluator: Evaluator = evaluate_relation
) -> dict[str, Any]:
    require(
        set(suite) == {"schema", "required_axes", "policies", "witnesses", "policy_pairs"},
        "suite field set mismatch",
    )
    require(
        suite.get("schema") == "protected-relation-discrimination.v0",
        "suite schema mismatch",
    )
    require(
        suite.get("required_axes") == list(REQUIRED_AXES),
        "REQUIRED_AXIS_SET_MISMATCH",
    )

    policies = suite.get("policies")
    witnesses = suite.get("witnesses")
    pairs = suite.get("policy_pairs")
    require(isinstance(policies, dict) and bool(policies), "policies must be a non-empty object")
    require(isinstance(witnesses, list) and bool(witnesses), "witnesses must be a non-empty array")
    require(isinstance(pairs, list) and bool(pairs), "policy_pairs must be a non-empty array")

    witness_map: dict[str, dict[str, Any]] = {}
    for witness in witnesses:
        require(
            isinstance(witness, dict) and set(witness) == {"witness_id", "before", "after"},
            "invalid witness shape",
        )
        witness_id = witness.get("witness_id")
        require(isinstance(witness_id, str) and bool(witness_id), "invalid witness_id")
        require(witness_id not in witness_map, f"duplicate witness_id: {witness_id}")
        witness_map[witness_id] = witness

    # Diagnose a missing load-bearing witness before matrix-coverage fallout in
    # an earlier pair can obscure the actual structural defect.
    for pair in pairs:
        if isinstance(pair, dict) and isinstance(pair.get("required_witnesses"), list):
            axis = pair.get("axis")
            require(
                all(witness_id in witness_map for witness_id in pair["required_witnesses"]),
                f"MISSING_REQUIRED_WITNESS:{axis}",
            )

    pair_axes: list[str] = []
    report_results: dict[str, Any] = {}
    for pair in pairs:
        require(
            isinstance(pair, dict)
            and set(pair)
            == {
                "axis",
                "left_policy",
                "right_policy",
                "required_witnesses",
                "expected_outcomes",
            },
            "invalid policy-pair shape",
        )
        axis = pair.get("axis")
        require(axis in REQUIRED_AXES, f"unsupported required axis: {axis}")
        require(axis not in pair_axes, f"duplicate policy pair for axis: {axis}")
        pair_axes.append(axis)

        left_id = pair.get("left_policy")
        right_id = pair.get("right_policy")
        require(left_id in policies and right_id in policies, f"unknown policy in pair: {axis}")
        left_policy = policies[left_id]
        right_policy = policies[right_id]
        require(isinstance(left_policy, dict) and isinstance(right_policy, dict), "policy must be an object")
        required_fields, allowed_fields = AXIS_POLICY_FIELDS[axis]
        differing_fields = _policy_diff(left_policy, right_policy)
        require(
            required_fields.issubset(differing_fields) and differing_fields.issubset(allowed_fields),
            f"POLICY_PAIR_NOT_AXIS_ISOLATED:{axis}:{sorted(differing_fields)}",
        )

        required_witnesses = pair.get("required_witnesses")
        require(
            isinstance(required_witnesses, list)
            and bool(required_witnesses)
            and all(witness_id in witness_map for witness_id in required_witnesses),
            f"MISSING_REQUIRED_WITNESS:{axis}",
        )
        require(
            len(required_witnesses) == len(set(required_witnesses)),
            f"duplicate required witness for axis: {axis}",
        )

        expectations = pair.get("expected_outcomes")
        require(isinstance(expectations, dict), f"expected_outcomes must be an object: {axis}")
        require(
            set(expectations) == set(witness_map),
            f"UNCLASSIFIED_WITNESS:{axis}",
        )
        for witness_id, expected in expectations.items():
            require(
                isinstance(expected, dict)
                and set(expected) == {"left", "right"}
                and expected.get("left") in OUTCOMES
                and expected.get("right") in OUTCOMES,
                f"invalid expected outcome: {axis}/{witness_id}",
            )
        require(
            all(
                expectations[witness_id]["left"] != expectations[witness_id]["right"]
                for witness_id in required_witnesses
            ),
            f"DECLARED_SEPARATION_MISSING:{axis}",
        )

        actuals: dict[str, dict[str, str]] = {}
        for witness_id, witness in witness_map.items():
            left_result = evaluator(deepcopy(left_policy), witness["before"], witness["after"])
            right_result = evaluator(deepcopy(right_policy), witness["before"], witness["after"])
            left_outcome = left_result.get("outcome")
            right_outcome = right_result.get("outcome")
            require(left_outcome in OUTCOMES, f"UNCLASSIFIED_EVALUATOR_OUTCOME:{axis}/{witness_id}/left")
            require(right_outcome in OUTCOMES, f"UNCLASSIFIED_EVALUATOR_OUTCOME:{axis}/{witness_id}/right")
            actuals[witness_id] = {
                "left": left_outcome,
                "right": right_outcome,
            }

        separating_witnesses = [
            witness_id
            for witness_id, actual in actuals.items()
            if actual["left"] != actual["right"]
        ]
        require(
            bool(separating_witnesses)
            and all(witness_id in separating_witnesses for witness_id in required_witnesses),
            f"UNRESOLVED_RELATION_DISCRIMINATION:{axis}",
        )

        for witness_id, actual in actuals.items():
            expected = expectations[witness_id]
            for side in ("left", "right"):
                mismatch = classify_outcome_mismatch(expected[side], actual[side])
                require(
                    mismatch == "MATCH",
                    f"{mismatch}:{axis}/{witness_id}/{side}:expected={expected[side]}:actual={actual[side]}",
                )

        report_results[axis] = {
            "status": "SEPARATED",
            "differing_policy_fields": sorted(differing_fields),
            "separating_witnesses": separating_witnesses,
            "outcomes": actuals,
        }

    require(pair_axes == list(REQUIRED_AXES), "REQUIRED_POLICY_PAIR_ORDER_OR_COVERAGE_MISMATCH")
    return {
        "status": "PASS",
        "required_axes": len(REQUIRED_AXES),
        "separated_axes": len(report_results),
        "witnesses": len(witness_map),
        "matrix": report_results,
    }


def validate_suite_file(path: Path = SUITE_PATH) -> dict[str, Any]:
    return validate_relation_discrimination(load_suite(path))
