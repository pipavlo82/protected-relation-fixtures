from __future__ import annotations

from collections import Counter
import json
import sys
from typing import Any

if __package__:
    from .contract import AdapterContractViolation, response_for, validate_request
else:
    from contract import AdapterContractViolation, response_for, validate_request


EXPECTED_KINDS = {
    "prf-001": "exact_neighborhood_identity",
    "prf-002": "exact_typed_relation",
    "prf-003": "verifier_status_class",
    "prf-004": "multiplicity_sensitive_relation",
    "prf-005": "composed_semantic_validity",
    "prf-006": "normalized_typed_relation",
}


def _result(
    request: dict[str, Any],
    outcome: str,
    reason_code: str,
    detail: str,
    evidence: list[dict[str, Any]],
) -> dict[str, Any]:
    return response_for(
        request,
        outcome=outcome,
        reason_code=reason_code,
        reason_detail=detail,
        evidence=evidence,
    )


def evaluate(request: dict[str, Any]) -> dict[str, Any]:
    request = validate_request(request)
    challenge_id = request["challenge_id"]
    expected_kind = EXPECTED_KINDS.get(challenge_id)
    if expected_kind is None:
        return _result(
            request,
            "UNVERIFIABLE",
            "UNSUPPORTED_CHALLENGE_CLASS",
            "The reference adapter has no declared evaluator for this challenge identifier.",
            [],
        )
    profile = request["protected_relation_profile"]
    if profile.get("kind") != expected_kind or profile.get("policy_version") != "v0":
        return _result(
            request,
            "UNVERIFIABLE",
            "UNSUPPORTED_PROTECTED_RELATION_PROFILE",
            "The benchmark-bound protected relation profile is unsupported.",
            [],
        )
    before = request["evaluation_input"]["before"]
    after = request["evaluation_input"]["after"]
    try:
        if challenge_id == "prf-001":
            preserved = set(before["A"]) == set(after["A"])
            return _result(
                request,
                "PRESERVED" if preserved else "VIOLATED",
                "EXACT_NEIGHBORHOOD_EQUAL" if preserved else "EXACT_NEIGHBORHOOD_DIFFERENT",
                "Compared the benchmark-bound exact neighbor identities.",
                [{"kind": "neighbor_count", "value": {"before": len(before["A"]), "after": len(after["A"])}}],
            )
        if challenge_id == "prf-002":
            fields = ("source", "relation", "target")
            preserved = tuple(before[field] for field in fields) == tuple(after[field] for field in fields)
            return _result(
                request,
                "PRESERVED" if preserved else "VIOLATED",
                "TYPED_RELATION_EQUAL" if preserved else "TYPED_RELATION_DIFFERENT",
                "Compared the directed typed relation triple exactly.",
                [{"kind": "compared_fields", "value": list(fields)}],
            )
        if challenge_id == "prf-003":
            justified = (
                before.get("status") == after.get("status")
                and before.get("reason") == after.get("reason")
                and after.get("reason_vocabulary_preserved") is True
            )
            if justified:
                return _result(
                    request,
                    "PRESERVED",
                    "STATUS_AND_REASON_PRESERVED",
                    "Status and declared reason vocabulary are preserved.",
                    [{"kind": "status", "value": before.get("status")}],
                )
            return _result(
                request,
                "UNVERIFIABLE",
                "STATUS_VOCABULARY_NOT_JUSTIFIED",
                "The response vocabulary does not justify a preservation or violation claim.",
                [{"kind": "vocabulary_preserved", "value": after.get("reason_vocabulary_preserved")}],
            )
        if challenge_id == "prf-004":
            def edge(row: dict[str, Any]) -> tuple[str, str, str]:
                return row["source"], row["relation"], row["target"]

            before_edges = Counter(edge(row) for row in before["links"])
            after_edges = Counter(edge(row) for row in after["links"])
            preserved = before_edges == after_edges
            return _result(
                request,
                "PRESERVED" if preserved else "VIOLATED",
                "MULTISET_RELATION_EQUAL" if preserved else "MULTISET_RELATION_DIFFERENT",
                "Compared directed typed edges with multiplicity.",
                [{"kind": "edge_count", "value": {"before": sum(before_edges.values()), "after": sum(after_edges.values())}}],
            )
        if challenge_id == "prf-005":
            predicate = before["protected_predicate"]
            field = predicate["path"]
            required = predicate["equals"]
            if before["state"].get(field) != required:
                return _result(
                    request,
                    "UNVERIFIABLE",
                    "BASELINE_PREDICATE_NOT_JUSTIFIED",
                    "The supplied baseline does not satisfy its protected predicate.",
                    [],
                )
            preserved = after["state"].get(field) == required
            return _result(
                request,
                "PRESERVED" if preserved else "VIOLATED",
                "COMPOSITION_SAFE" if preserved else "COMPOSITION_BREAKS_PROTECTED_PREDICATE",
                "Evaluated the declared protected predicate after ordered composition.",
                [{"kind": "protected_field", "value": field}],
            )
        normalization = profile.get("normalization")
        if not isinstance(normalization, dict):
            raise KeyError("normalization")
        identities = normalization["identity_aliases"]
        relations = normalization["relation_aliases"]

        def normalized(state: dict[str, Any]) -> tuple[str, str, str]:
            return (
                identities[state["source"]],
                relations[state["relation"]],
                identities[state["target"]],
            )

        preserved = normalized(before) == normalized(after)
        return _result(
            request,
            "PRESERVED" if preserved else "VIOLATED",
            "NORMALIZED_RELATION_EQUAL" if preserved else "NORMALIZED_RELATION_DIFFERENT",
            "Applied only benchmark-declared identity and relation aliases.",
            [{"kind": "normalization_profile_digest", "value": request["protected_relation_profile_digest"]}],
        )
    except (KeyError, TypeError, ValueError) as exc:
        return _result(
            request,
            "UNVERIFIABLE",
            "INSUFFICIENT_SEMANTIC_INPUT",
            f"The reference adapter could not justify the requested comparison: {exc}",
            [],
        )


def main() -> int:
    try:
        request = json.loads(sys.stdin.read())
        response = evaluate(request)
    except (json.JSONDecodeError, AdapterContractViolation) as exc:
        print(f"reference adapter failure: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(response, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
