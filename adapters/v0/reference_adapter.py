from __future__ import annotations

from collections import Counter
import json
import sys
from typing import Any

if __package__:
    from .contract import AdapterContractViolation, validate_evaluator_output, validate_request
else:
    from contract import AdapterContractViolation, validate_evaluator_output, validate_request


EXPECTED_KINDS = {
    "prf-001": "exact_neighborhood_identity",
    "prf-002": "exact_typed_relation",
    "prf-003": "verifier_status_class",
    "prf-004": "multiplicity_sensitive_relation",
    "prf-005": "composed_semantic_validity",
    "prf-006": "normalized_typed_relation",
}


def _result(outcome: str, detail: str) -> dict[str, Any]:
    return validate_evaluator_output({"outcome": outcome, "reason_detail": detail})


def evaluate(request: dict[str, Any]) -> dict[str, Any]:
    request = validate_request(request)
    challenge_id = request["challenge_id"]
    expected_kind = EXPECTED_KINDS.get(challenge_id)
    if expected_kind is None:
        return _result(
            "UNVERIFIABLE",
            "The reference evaluator has no declared evaluator for this challenge identifier.",
        )
    profile = request["protected_relation_profile"]
    if profile.get("kind") != expected_kind or profile.get("policy_version") != "v0":
        return _result(
            "UNVERIFIABLE",
            "The benchmark-bound protected relation profile is unsupported.",
        )
    before = request["evaluation_input"]["before"]
    after = request["evaluation_input"]["after"]
    try:
        if challenge_id == "prf-001":
            preserved = set(before["A"]) == set(after["A"])
            return _result(
                "PRESERVED" if preserved else "VIOLATED",
                "Compared the benchmark-bound exact neighbor identities.",
            )
        if challenge_id == "prf-002":
            fields = ("source", "relation", "target")
            preserved = tuple(before[field] for field in fields) == tuple(after[field] for field in fields)
            return _result(
                "PRESERVED" if preserved else "VIOLATED",
                "Compared the directed typed relation triple exactly.",
            )
        if challenge_id == "prf-003":
            justified = (
                before.get("status") == after.get("status")
                and before.get("reason") == after.get("reason")
                and after.get("reason_vocabulary_preserved") is True
            )
            if justified:
                return _result("PRESERVED", "Status and declared reason vocabulary are preserved.")
            return _result(
                "UNVERIFIABLE",
                "The response vocabulary does not justify a preservation or violation claim.",
            )
        if challenge_id == "prf-004":
            def edge(row: dict[str, Any]) -> tuple[str, str, str]:
                return row["source"], row["relation"], row["target"]

            before_edges = Counter(edge(row) for row in before["links"])
            after_edges = Counter(edge(row) for row in after["links"])
            return _result(
                "PRESERVED" if before_edges == after_edges else "VIOLATED",
                "Compared directed typed edges with multiplicity.",
            )
        if challenge_id == "prf-005":
            predicate = before["protected_predicate"]
            field = predicate["path"]
            required = predicate["equals"]
            if before["state"].get(field) != required:
                return _result(
                    "UNVERIFIABLE",
                    "The supplied baseline does not satisfy its protected predicate.",
                )
            preserved = after["state"].get(field) == required
            return _result(
                "PRESERVED" if preserved else "VIOLATED",
                "Evaluated the declared protected predicate after ordered composition.",
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
            "PRESERVED" if preserved else "VIOLATED",
            "Applied only benchmark-declared identity and relation aliases.",
        )
    except (KeyError, TypeError, ValueError) as exc:
        return _result(
            "UNVERIFIABLE",
            f"The reference evaluator could not justify the requested comparison: {exc}",
        )


def main() -> int:
    try:
        request = json.loads(sys.stdin.read())
        evaluator_output = evaluate(request)
    except (json.JSONDecodeError, AdapterContractViolation) as exc:
        print(f"reference evaluator failure: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(evaluator_output, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
