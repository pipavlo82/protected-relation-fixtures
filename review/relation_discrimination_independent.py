from __future__ import annotations

import argparse
from collections import Counter
from copy import deepcopy
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import subprocess
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SUITE_PATH = ROOT / "conformance" / "relation-discrimination-v0" / "suite.json"
BASE_SHA = "154d35d0a4748da2ef40332e310a01d1549948fa"
HEAD_SHA = "b14d63e0d8f869c0b7aa0efdb1d2a0a23ed6dd68"
AXES = ("identity", "relation_type", "multiplicity", "direction", "scope")
OUTCOMES = {"PRESERVED", "VIOLATED", "UNVERIFIABLE"}
STRICT_VALUE = {
    "identity": "anchored",
    "relation_type": "typed-exact",
    "multiplicity": "multiset-exact",
    "direction": "directed-exact",
    "scope": "global",
}
AXIS_FIELDS = {
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


class ReviewError(ValueError):
    pass


class NotJustified(ValueError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ReviewError(message)


@dataclass(frozen=True)
class Evaluation:
    outcome: str
    reason: str

    def as_json(self) -> dict[str, str]:
        return {"outcome": self.outcome, "reason": self.reason}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_declared_suite() -> dict[str, Any]:
    raw = SUITE_PATH.read_bytes()
    require(raw.endswith(b"\n") and b"\r" not in raw, "suite byte framing is not LF-only")
    try:
        value = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ReviewError(f"suite is not valid UTF-8 JSON: {exc}") from exc
    require(isinstance(value, dict), "suite root is not an object")
    return value


def selected_policy_value(
    policy: dict[str, Any], axis: str, field: str, mutation: str | None
) -> Any:
    if mutation == axis:
        return STRICT_VALUE[axis]
    return policy.get(field)


def mapped_value(mapping: Any, raw: Any, failure_prefix: str) -> str:
    if not isinstance(raw, str) or not raw:
        raise NotJustified(f"{failure_prefix}-input-invalid")
    if not isinstance(mapping, dict):
        raise NotJustified(f"{failure_prefix}-map-missing")
    canonical = mapping.get(raw)
    if not isinstance(canonical, str) or not canonical:
        raise NotJustified(f"{failure_prefix}-undeclared:{raw}")
    return canonical


def normalize_identity(
    policy: dict[str, Any], raw: Any, mutation: str | None
) -> str:
    if not isinstance(raw, str) or not raw:
        raise NotJustified("identity-input-invalid")
    mode = selected_policy_value(policy, "identity", "identity_policy", mutation)
    if mode == "anchored":
        return raw
    if mode == "alias-permitted":
        return mapped_value(policy.get("identity_aliases"), raw, "identity-alias")
    raise NotJustified(f"identity-policy-unsupported:{mode}")


def normalize_relation_type(
    policy: dict[str, Any], raw: Any, mutation: str | None
) -> str:
    if not isinstance(raw, str) or not raw:
        raise NotJustified("relation-type-input-invalid")
    mode = selected_policy_value(
        policy,
        "relation_type",
        "relation_type_policy",
        mutation,
    )
    if mode == "typed-exact":
        return raw
    if mode == "type-ignored":
        return "<relation-type-ignored>"
    if mode == "type-normalized":
        return mapped_value(
            policy.get("relation_type_aliases"),
            raw,
            "relation-type-alias",
        )
    raise NotJustified(f"relation-type-policy-unsupported:{mode}")


def canonicalize_state(
    policy: dict[str, Any], state: dict[str, Any], mutation: str | None = None
) -> tuple[tuple[tuple[str, str, str, str], int], ...]:
    if not isinstance(policy, dict) or policy.get("kind") != "edge-relation":
        raise NotJustified("policy-kind-unsupported")
    if set(policy) != POLICY_FIELDS:
        raise NotJustified("policy-field-set-unsupported")
    if not isinstance(state, dict) or set(state) != {"complete_scopes", "relations"}:
        raise NotJustified("state-field-set-invalid")

    complete_scopes = state.get("complete_scopes")
    relations = state.get("relations")
    if (
        not isinstance(complete_scopes, list)
        or not complete_scopes
        or not all(isinstance(item, str) and item for item in complete_scopes)
        or len(complete_scopes) != len(set(complete_scopes))
        or not isinstance(relations, list)
    ):
        raise NotJustified("semantic-input-incomplete")

    scope_mode = selected_policy_value(policy, "scope", "scope_policy", mutation)
    if scope_mode == "global":
        if "global" not in complete_scopes:
            raise NotJustified("global-scope-incomplete")
        scope_filter = None
    elif scope_mode == "local-bounded":
        scope_filter = policy.get("scope_anchor")
        if not isinstance(scope_filter, str) or not scope_filter:
            raise NotJustified("local-scope-anchor-missing")
        if scope_filter not in complete_scopes:
            raise NotJustified(f"local-scope-incomplete:{scope_filter}")
    else:
        raise NotJustified(f"scope-policy-unsupported:{scope_mode}")

    direction_mode = selected_policy_value(
        policy,
        "direction",
        "direction_policy",
        mutation,
    )
    if direction_mode not in {"directed-exact", "direction-ignored"}:
        raise NotJustified(f"direction-policy-unsupported:{direction_mode}")
    multiplicity_mode = selected_policy_value(
        policy,
        "multiplicity",
        "multiplicity_policy",
        mutation,
    )
    if multiplicity_mode not in {"multiset-exact", "set-collapsed"}:
        raise NotJustified(f"multiplicity-policy-unsupported:{multiplicity_mode}")

    edges: list[tuple[str, str, str, str]] = []
    for relation in relations:
        if not isinstance(relation, dict) or set(relation) != {
            "source",
            "relation_type",
            "target",
            "scope",
        }:
            raise NotJustified("relation-record-invalid")
        relation_scope = relation.get("scope")
        if not isinstance(relation_scope, str) or not relation_scope:
            raise NotJustified("relation-scope-invalid")
        if scope_filter is not None and relation_scope != scope_filter:
            continue

        source = normalize_identity(policy, relation.get("source"), mutation)
        target = normalize_identity(policy, relation.get("target"), mutation)
        relation_type = normalize_relation_type(
            policy,
            relation.get("relation_type"),
            mutation,
        )
        if direction_mode == "direction-ignored":
            source, target = sorted((source, target))
        edges.append((relation_scope, source, relation_type, target))

    counts = Counter(edges)
    if multiplicity_mode == "set-collapsed":
        counts = Counter({edge: 1 for edge in counts})
    return tuple(sorted(counts.items()))


def phi(
    policy: dict[str, Any], state: dict[str, Any], mutation: str | None = None
) -> tuple[bool, Any]:
    try:
        return True, canonicalize_state(policy, state, mutation)
    except NotJustified as exc:
        return False, str(exc)


def compare(
    before: tuple[bool, Any], after: tuple[bool, Any]
) -> Evaluation:
    if not before[0]:
        return Evaluation("UNVERIFIABLE", f"before:{before[1]}")
    if not after[0]:
        return Evaluation("UNVERIFIABLE", f"after:{after[1]}")
    if before[1] == after[1]:
        return Evaluation("PRESERVED", "canonical-semantic-objects-equal")
    return Evaluation("VIOLATED", "canonical-semantic-objects-differ")


def evaluate(
    policy: dict[str, Any],
    before: dict[str, Any],
    after: dict[str, Any],
    mutation: str | None = None,
) -> Evaluation:
    return compare(phi(policy, before, mutation), phi(policy, after, mutation))


def mismatch_class(expected: str, actual: str) -> str:
    require(expected in OUTCOMES and actual in OUTCOMES, "outcome label unsupported")
    if expected == actual:
        return "MATCH"
    mapping = {
        ("VIOLATED", "PRESERVED"): "UNSAFE_FALSE_PRESERVATION",
        ("UNVERIFIABLE", "PRESERVED"): "UNSAFE_UNVERIFIABLE_UPGRADE",
        ("PRESERVED", "VIOLATED"): "FALSE_VIOLATION",
        ("PRESERVED", "UNVERIFIABLE"): "PRESERVATION_NOT_ESTABLISHED",
        ("VIOLATED", "UNVERIFIABLE"): "VIOLATION_NOT_ESTABLISHED",
        ("UNVERIFIABLE", "VIOLATED"): "UNVERIFIABLE_MISCLASSIFIED_AS_VIOLATION",
    }
    return mapping[(expected, actual)]


def policy_diff(left: dict[str, Any], right: dict[str, Any]) -> set[str]:
    return {
        field
        for field in set(left) | set(right)
        if left.get(field) != right.get(field)
    }


def run_suite(
    suite: dict[str, Any], mutation: str | None = None
) -> dict[str, Any]:
    require(suite.get("schema") == "protected-relation-discrimination.v0", "schema mismatch")
    require(suite.get("required_axes") == list(AXES), "required axis set mismatch")
    policies = suite.get("policies")
    witnesses = suite.get("witnesses")
    pairs = suite.get("policy_pairs")
    require(isinstance(policies, dict), "policies missing")
    require(isinstance(witnesses, list), "witnesses missing")
    require(isinstance(pairs, list), "policy pairs missing")

    witness_map: dict[str, dict[str, Any]] = {}
    for witness in witnesses:
        require(isinstance(witness, dict), "witness is not an object")
        witness_id = witness.get("witness_id")
        require(isinstance(witness_id, str) and witness_id, "witness id invalid")
        require(witness_id not in witness_map, f"duplicate witness:{witness_id}")
        witness_map[witness_id] = witness

    for pair in pairs:
        if isinstance(pair, dict) and isinstance(pair.get("required_witnesses"), list):
            missing = set(pair["required_witnesses"]) - set(witness_map)
            require(not missing, f"MISSING_REQUIRED_WITNESS:{pair.get('axis')}:{sorted(missing)}")

    matrix: dict[str, Any] = {}
    seen_axes: list[str] = []
    all_expectations_match = True
    for pair in pairs:
        require(isinstance(pair, dict), "policy pair is not an object")
        axis = pair.get("axis")
        require(axis in AXES and axis not in seen_axes, f"policy pair axis invalid:{axis}")
        seen_axes.append(axis)
        left_id = pair.get("left_policy")
        right_id = pair.get("right_policy")
        require(left_id in policies and right_id in policies, f"policy reference invalid:{axis}")
        left_policy = policies[left_id]
        right_policy = policies[right_id]

        required_change, permitted_changes = AXIS_FIELDS[axis]
        changed = policy_diff(left_policy, right_policy)
        require(
            required_change.issubset(changed) and changed.issubset(permitted_changes),
            f"POLICY_PAIR_NOT_AXIS_ISOLATED:{axis}:{sorted(changed)}",
        )

        required_witnesses = pair.get("required_witnesses")
        expectations = pair.get("expected_outcomes")
        require(
            isinstance(required_witnesses, list) and required_witnesses,
            f"required witnesses invalid:{axis}",
        )
        require(
            isinstance(expectations, dict) and set(expectations) == set(witness_map),
            f"expected matrix coverage invalid:{axis}",
        )

        results: dict[str, Any] = {}
        separators: list[str] = []
        for witness_id, witness in witness_map.items():
            left = evaluate(left_policy, witness["before"], witness["after"], mutation)
            right = evaluate(right_policy, witness["before"], witness["after"], mutation)
            expected = expectations[witness_id]
            left_class = mismatch_class(expected["left"], left.outcome)
            right_class = mismatch_class(expected["right"], right.outcome)
            if left_class != "MATCH" or right_class != "MATCH":
                all_expectations_match = False
            if left.outcome != right.outcome:
                separators.append(witness_id)
            results[witness_id] = {
                "left": left.as_json(),
                "right": right.as_json(),
                "declared_expected": deepcopy(expected),
                "comparison": {"left": left_class, "right": right_class},
            }

        required_are_separators = all(
            witness_id in separators for witness_id in required_witnesses
        )
        axis_status = (
            "SEPARATED"
            if separators and required_are_separators
            else "UNRESOLVED_RELATION_DISCRIMINATION"
        )
        matrix[axis] = {
            "status": axis_status,
            "left_policy": left_id,
            "right_policy": right_id,
            "differing_policy_fields": sorted(changed),
            "required_witnesses": list(required_witnesses),
            "separating_witnesses": separators,
            "results": results,
        }

    require(seen_axes == list(AXES), "policy pair coverage/order mismatch")
    separated = sum(row["status"] == "SEPARATED" for row in matrix.values())
    return {
        "matrix": matrix,
        "separated_axes": separated,
        "required_axes": len(AXES),
        "witnesses": len(witness_map),
        "policy_pair_witness_side_outcomes": len(pairs) * len(witness_map) * 2,
        "expected_matrix_matches": all_expectations_match,
        "status": (
            "REPRODUCED"
            if separated == len(AXES) and all_expectations_match
            else "DIVERGED"
        ),
    }


def run_negative_controls(suite: dict[str, Any]) -> dict[str, Any]:
    controls: dict[str, Any] = {}
    for axis in AXES:
        mutated = run_suite(suite, mutation=axis)
        observed = mutated["matrix"][axis]["status"]
        controls[f"collapse_{axis}"] = {
            "observed": observed,
            "killed": observed == "UNRESOLVED_RELATION_DISCRIMINATION",
        }

    missing_witness_suite = deepcopy(suite)
    missing_witness_suite["witnesses"] = [
        witness
        for witness in missing_witness_suite["witnesses"]
        if witness["witness_id"] != "direction-reversal"
    ]
    try:
        run_suite(missing_witness_suite)
        missing_witness_result = "NOT_REJECTED"
    except ReviewError as exc:
        missing_witness_result = str(exc)
    controls["missing_required_witness"] = {
        "observed": missing_witness_result,
        "killed": missing_witness_result.startswith("MISSING_REQUIRED_WITNESS"),
    }

    first_witness = suite["witnesses"][0]
    unsupported_policy = deepcopy(suite["policies"]["strict-global"])
    unsupported_policy["direction_policy"] = "future-unknown-direction"
    unsupported_result = evaluate(
        unsupported_policy,
        first_witness["before"],
        first_witness["after"],
    )
    controls["unsupported_policy_value"] = {
        "observed": unsupported_result.as_json(),
        "killed": unsupported_result.outcome == "UNVERIFIABLE",
    }

    witness_by_id = {witness["witness_id"]: witness for witness in suite["witnesses"]}
    undeclared = witness_by_id["undeclared-alias"]
    undeclared_result = evaluate(
        suite["policies"]["alias-global"],
        undeclared["before"],
        undeclared["after"],
    )
    controls["undeclared_identity_alias"] = {
        "observed": undeclared_result.as_json(),
        "killed": undeclared_result.outcome == "UNVERIFIABLE",
    }

    incomplete = witness_by_id["incomplete-global-scope"]
    incomplete_result = evaluate(
        suite["policies"]["strict-global"],
        incomplete["before"],
        incomplete["after"],
    )
    controls["incomplete_global_scope"] = {
        "observed": incomplete_result.as_json(),
        "killed": incomplete_result.outcome == "UNVERIFIABLE",
    }

    unsafe_false = mismatch_class("VIOLATED", "PRESERVED")
    controls["unsafe_false_preservation"] = {
        "observed": unsafe_false,
        "killed": unsafe_false == "UNSAFE_FALSE_PRESERVATION",
    }
    unsafe_unknown = mismatch_class("UNVERIFIABLE", "PRESERVED")
    controls["unsafe_unverifiable_upgrade"] = {
        "observed": unsafe_unknown,
        "killed": unsafe_unknown == "UNSAFE_UNVERIFIABLE_UPGRADE",
    }

    return {
        "artifact_schema": "relation-discrimination-independent-negative-controls.v0",
        "review_mode": "NON_BLIND_SECOND_IMPLEMENTATION",
        "controls": controls,
        "passed": sum(row["killed"] for row in controls.values()),
        "total": len(controls),
        "status": "PASS" if all(row["killed"] for row in controls.values()) else "FAIL",
    }


def exact_git_head() -> str:
    return subprocess.check_output(
        ["git", "rev-parse", "HEAD"],
        cwd=ROOT,
        text=True,
    ).strip()


def write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def first_run_artifact(suite: dict[str, Any]) -> dict[str, Any]:
    head = exact_git_head()
    require(head == HEAD_SHA, f"wrong PR head:{head}")
    result = run_suite(suite)
    return {
        "artifact_schema": "relation-discrimination-independent-first-run.v0",
        "review_mode": "NON_BLIND_SECOND_IMPLEMENTATION",
        "blindness_disclosure": (
            "Reviewer had inspected the candidate implementation during an earlier task; "
            "this run is not blind."
        ),
        "base_sha": BASE_SHA,
        "pr_head_sha": head,
        "contract_sources": [
            "spec/relation-discrimination-v0.md",
            "conformance/relation-discrimination-v0/suite.json",
        ],
        "candidate_implementation_imported": False,
        "suite_sha256": sha256(SUITE_PATH),
        "independent_implementation_sha256": sha256(Path(__file__)),
        **result,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path)
    parser.add_argument("--negative-controls-output", type=Path)
    args = parser.parse_args()
    require(bool(args.output) != bool(args.negative_controls_output), "select exactly one output mode")
    suite = load_declared_suite()
    if args.output:
        artifact = first_run_artifact(suite)
        write_json(args.output, artifact)
        print(
            f"{artifact['status']}: "
            f"{artifact['separated_axes']}/{artifact['required_axes']} axes; "
            f"expected_matrix_matches={artifact['expected_matrix_matches']}"
        )
        return 0 if artifact["status"] == "REPRODUCED" else 1
    controls = run_negative_controls(suite)
    write_json(args.negative_controls_output, controls)
    print(f"negative controls: {controls['status']} ({controls['passed']}/{controls['total']})")
    return 0 if controls["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
