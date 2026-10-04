"""Experimental neutral contract consumer; domain semantics live in adapters."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from jsonschema import Draft202012Validator

VERSION = "guarantee-preservation-v0"
ROOT = Path(__file__).resolve().parents[1]
PROFILE = ROOT / "conformance" / VERSION
SCHEMA_PATH = PROFILE / "contract.schema.json"
SCHEMA_SHA256 = "44229b0a8322b4fe2f2c2946e0fa705e64c9bee4565693276e7db53155c5ae31"


class ContractError(ValueError):
    pass


def require(condition, reason):
    if not condition:
        raise ContractError(reason)


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
                      allow_nan=False).encode("utf-8")


def digest(value):
    return "sha256:" + hashlib.sha256(canonical(value)).hexdigest()


def _unique(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, "duplicate_json_key:" + key)
        result[key] = value
    return result


def parse_json(raw):
    return json.loads(raw.decode("utf-8"), object_pairs_hook=_unique,
                      parse_constant=lambda value: (_ for _ in ()).throw(ContractError("nonfinite_json")))


def load_json(path):
    return parse_json(Path(path).read_bytes())


def validate_schema(envelope):
    raw = SCHEMA_PATH.read_bytes()
    require(hashlib.sha256(raw).hexdigest() == SCHEMA_SHA256, "unsupported_schema_digest")
    schema = parse_json(raw)
    Draft202012Validator.check_schema(schema)
    errors = sorted(Draft202012Validator(schema).iter_errors(envelope), key=lambda e: str(e.path))
    require(not errors, "invalid_contract_shape")


def _check_basis(basis, policy, evaluator):
    require(isinstance(basis, dict) and basis.get("schema_version") == VERSION,
            "unsupported_dependency_basis")
    require(basis.get("context") == policy["context"], "basis_context_mismatch")
    # This is an explicitly accepted, bounded premise supplied by the consumer.
    # No digest or producer statement establishes its completeness or soundness.
    acceptance = basis.get("acceptance", {})
    require(isinstance(acceptance, dict), "invalid_basis_acceptance")
    require(acceptance.get("status") == "ACCEPTED_BOUNDED"
            and isinstance(acceptance.get("acceptance_ref"), str)
            and bool(acceptance["acceptance_ref"].strip()), "basis_not_separately_accepted")
    require(basis.get("rule") == "all-required-relations-v0", "unsupported_basis_rule")
    dependencies = basis.get("mandatory")
    require(isinstance(dependencies, dict) and bool(dependencies), "empty_dependency_basis")
    require(set(dependencies) == set(evaluator.dependencies), "unsupported_basis_dependencies")
    for name, specification in dependencies.items():
        require(isinstance(specification, dict)
                and specification.get("evaluator_ref") == evaluator.evaluator_ref,
                "unknown_dependency_evaluator")
        edges = specification.get("requires")
        require(isinstance(edges, list) and len(edges) == len(set(edges))
                and all(edge in dependencies for edge in edges), "unknown_basis_edge")
    visiting, visited = set(), set()
    def visit(name):
        require(name not in visiting, "circular_dependency_basis")
        if name in visited:
            return
        visiting.add(name)
        for edge in dependencies[name]["requires"]:
            visit(edge)
        visiting.remove(name)
        visited.add(name)
    for name in dependencies:
        visit(name)
    return dependencies


def _safe_digest(value):
    try:
        return digest(value)
    except (TypeError, ValueError):
        return None


def _decision(policy, outcome, reason, envelope=None, checks=None):
    observed = envelope if isinstance(envelope, dict) else {}
    selected = policy if isinstance(policy, dict) else {}
    return {"schema_version": VERSION,
            "context": selected.get("context"), "policy_digest": _safe_digest(selected),
            "observation_bindings": {key: observed.get(key) for key in
                                     ("adapter_ref", "evaluator_ref", "context", "dependency_basis")},
            "envelope_digest": _safe_digest(envelope),
            "evidence_digests": [{"ref": item.get("ref"), "digest": item.get("digest")}
                                 for item in observed.get("evidence", []) if isinstance(item, dict)]
                                 if isinstance(observed.get("evidence", []), list) else [],
            "policy_id": policy.get("id") if isinstance(policy, dict) else None,
            "outcome": outcome, "reason": reason,
            "guarantee": policy["context"]["guarantee_id"] if outcome == "PRESERVED" else None,
            "native": envelope.get("native") if isinstance(envelope, dict) else None,
            "checks": checks or [],
            "establishes": [policy["context"]["guarantee_id"]] if outcome == "PRESERVED" else [],
            "does_not_establish": envelope.get("does_not_establish", []) if isinstance(envelope, dict) else []}


def consume(envelope, *, policy, accepted_basis, registry):
    """Caller selects trusted policy, accepted basis and evaluator registry separately.

    These arguments are the bounded trust boundary; this function cannot establish
    who accepted them. Producer refs, accepted flags and hashes confer no authority.
    """
    try:
        validate_schema(envelope)
        require(isinstance(policy, dict) and policy.get("schema_version") == VERSION
                and policy.get("conflict_rule") == "withhold"
                and policy.get("aggregation_rule") == "all-required-relations-v0",
                "unsupported_consumer_policy")
        require(isinstance(policy.get("id"), str) and bool(policy["id"].strip()),
                "consumer_policy_identity_required")
        for field in ("allowed_adapters", "allowed_evidence_classes"):
            values = policy.get(field)
            require(isinstance(values, list)
                    and all(isinstance(value, str) and bool(value.strip()) for value in values)
                    and len(values) == len(set(values)), "invalid_consumer_policy_allowlist")
        require(isinstance(registry, dict), "trusted_evaluator_registry_required")
        require(envelope["context"] == policy.get("context"), "context_binding_mismatch")
        require(envelope["adapter_ref"] in policy.get("allowed_adapters", []), "adapter_not_authorized")
        evaluator = registry.get(envelope["adapter_ref"])
        require(evaluator is not None and getattr(evaluator, "evaluator_ref", None) == envelope["evaluator_ref"]
                and callable(getattr(evaluator, "verify", None)),
                "unknown_evaluator")
        require(isinstance(accepted_basis, dict), "unsupported_dependency_basis")
        basis_digest = digest(accepted_basis)
        require(policy.get("accepted_basis_digest") == basis_digest
                and envelope["dependency_basis"] == {"id": accepted_basis.get("id"), "digest": basis_digest},
                "dependency_basis_binding_mismatch")
        dependencies = _check_basis(accepted_basis, policy, evaluator)
        depends_on = envelope["depends_on"]
        require(bool(depends_on), "empty_dependencies")
        require(len(depends_on) == len(set(depends_on))
                and set(depends_on) == set(dependencies), "mandatory_dependency_coverage")
        require(envelope["depends_on_digest"] == digest(depends_on), "dependency_digest_mismatch")
        require(envelope["evidence_class"] in policy.get("allowed_evidence_classes", []),
                "evidence_class_not_admitted")
        require(envelope["evidence_class"] in getattr(evaluator, "evidence_classes", ()),
                "evidence_class_not_supported_by_adapter")
        # Adapters validate applicability/admissibility and recompute their exact
        # declared predicates. The neutral consumer has no case-name branches.
        verified = evaluator.verify(envelope)
        require(verified["applicable"] is True, "relation_not_applicable")
        require(verified["admissible"] is True, "evidence_not_admissible")
        require(envelope["context"] == verified["context"], "adapter_context_mismatch")
        require(envelope["native"] == verified["native"], "native_payload_mismatch")
        require(envelope["does_not_establish"] == verified["does_not_establish"],
                "unsupported_guarantee_promotion")
        observed = {}
        for check in envelope["checks"]:
            name = check["dependency_id"]
            require(name in dependencies, "unknown_mandatory_dependency")
            observed.setdefault(name, []).append(check)
        require(set(observed) == set(dependencies), "missing_dependency_evidence")
        resolved = []
        for name in sorted(dependencies):
            witnesses = observed[name]
            require(len({w["outcome"] for w in witnesses}) == 1, "conflicting_evidence")
            expected = verified["checks"][name]
            for witness in witnesses:
                require(witness == expected, "check_evidence_mismatch")
            # Exact duplicate corroboration is allowed; it is not another native
            # economic settlement event and does not change the relation's arity.
            resolved.append(expected)
        if any(check["outcome"] == "UNKNOWN" for check in resolved):
            return _decision(policy, "UNVERIFIABLE", "required_relation_unestablished", envelope, resolved)
        if any(check["outcome"] == "FALSE" for check in resolved):
            return _decision(policy, "VIOLATED", "bound_relation_refuted", envelope, resolved)
        return _decision(policy, "PRESERVED", "required_relations_established", envelope, resolved)
    except (ContractError, KeyError, TypeError, ValueError, OSError) as exc:
        return _decision(policy, "UNVERIFIABLE", str(exc), envelope)


def select_inputs(envelope, *, policy_id, configuration):
    """Resolve consumer-owned fixture configuration; never select from envelope."""
    require(policy_id in configuration["policies"], "unknown_consumer_policy")
    policy = configuration["policies"][policy_id]
    basis = configuration["accepted_bases"][policy["basis_id"]]
    return policy, basis
