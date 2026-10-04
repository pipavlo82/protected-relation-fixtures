"""Named, in-memory source mutations for the bounded guarantee consumer."""
from __future__ import annotations

import copy
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import re
from typing import Callable, Mapping, Any


ROOT = Path(__file__).resolve().parents[1]
DECISION_KEYS = {
    "schema_version", "policy_id", "outcome", "reason", "guarantee", "native",
    "checks", "establishes", "does_not_establish", "context", "policy_digest",
    "observation_bindings", "envelope_digest", "evidence_digests",
}
OBSERVATION_BINDING_KEYS = {"adapter_ref", "evaluator_ref", "context", "dependency_basis"}
OUTCOMES = {"PRESERVED", "VIOLATED", "UNVERIFIABLE"}


@dataclass(frozen=True)
class Replacement:
    old: str
    new: str


@dataclass(frozen=True)
class Mutation:
    name: str
    source_path: str
    replacements: tuple[Replacement, ...]
    adverse_test: str
    positive_control: str


def _hash(source: str) -> str:
    return hashlib.sha256(source.encode("utf-8")).hexdigest()


def _digest_reference(value: Any) -> bool:
    return value is None or (isinstance(value, str) and re.fullmatch(r"sha256:[0-9a-f]{64}", value) is not None)


def _valid_decision(value: Any) -> bool:
    if not isinstance(value, dict) or set(value) != DECISION_KEYS:
        return False
    if (value["schema_version"] != "guarantee-preservation-v0"
            or not isinstance(value["outcome"], str) or value["outcome"] not in OUTCOMES):
        return False
    if any(value[key] is not None and not isinstance(value[key], str)
           for key in ("policy_id", "guarantee")):
        return False
    if not isinstance(value["reason"], str) or not value["reason"]:
        return False
    if not all(isinstance(value[key], list) for key in ("checks", "establishes", "does_not_establish")):
        return False
    if value["native"] is not None and not isinstance(value["native"], dict):
        return False
    if value["context"] is not None and not isinstance(value["context"], dict):
        return False
    if not all(_digest_reference(value[key]) for key in ("policy_digest", "envelope_digest")):
        return False
    bindings = value["observation_bindings"]
    if not isinstance(bindings, dict) or set(bindings) != OBSERVATION_BINDING_KEYS:
        return False
    if any(bindings[key] is not None and not isinstance(bindings[key], str)
           for key in ("adapter_ref", "evaluator_ref")):
        return False
    if any(bindings[key] is not None and not isinstance(bindings[key], dict)
           for key in ("context", "dependency_basis")):
        return False
    evidence = value["evidence_digests"]
    if not isinstance(evidence, list) or any(
        not isinstance(item, dict) or set(item) != {"ref", "digest"}
        or (item["ref"] is not None and not isinstance(item["ref"], str))
        or not _digest_reference(item["digest"]) for item in evidence
    ):
        return False
    try:
        json.dumps(value, allow_nan=False)
    except (TypeError, ValueError):
        return False
    return True


def _load_source(source: str, path: str) -> dict[str, Any]:
    namespace = {"__name__": "_prf_guarantee_mutation", "__file__": str(ROOT / path)}
    exec(compile(source, str(ROOT / path), "exec"), namespace)
    return namespace


def _probe(namespace, name, runner, expectation):
    try:
        decision = runner(namespace, name)
    except Exception as exc:
        return {"state": "CRASHED", "exception": type(exc).__name__}
    if not _valid_decision(decision):
        return {"state": "INVALID_OUTPUT"}
    matched = all(decision.get(key) == expected for key, expected in expectation.items())
    return {"state": "VALID", "outcome": decision["outcome"], "matched": matched}


def run_mutation(
    mutation: Mutation,
    *,
    source_text: str,
    probe_runner: Callable,
    expectations: Mapping[str, dict],
) -> dict[str, Any]:
    """A kill requires an adverse semantic failure and a preserved positive.

    Syntax errors, crashes, invalid outputs, unapplied replacements and damaged
    positive controls are diagnostic failures, never successful mutation kills.
    """
    report = {
        "id": mutation.name,
        "source_path": mutation.source_path,
        "source_sha256": _hash(source_text),
        "mutated_sha256": None,
        "adverse_test": mutation.adverse_test,
        "positive_control": mutation.positive_control,
        "status": "UNAPPLIED",
        "observations": {},
    }
    names = (mutation.positive_control, mutation.adverse_test)
    if (names[0] == names[1] or not mutation.replacements
            or any(name not in expectations or not expectations[name] for name in names)):
        report["status"] = "INVALID_SPEC"
        return report
    mutated_source = source_text
    for replacement in mutation.replacements:
        if not replacement.old or mutated_source.count(replacement.old) != 1:
            return report
        mutated_source = mutated_source.replace(replacement.old, replacement.new, 1)
    if mutated_source == source_text:
        return report
    report["mutated_sha256"] = _hash(mutated_source)
    try:
        baseline = _load_source(source_text, mutation.source_path)
    except Exception as exc:
        report["status"] = "BASELINE_FAILED"
        report["exception"] = type(exc).__name__
        return report
    baseline_probes = {
        name: _probe(baseline, name, probe_runner, copy.deepcopy(expectations[name]))
        for name in names
    }
    report["observations"]["baseline"] = baseline_probes
    if any(value["state"] != "VALID" or not value["matched"] for value in baseline_probes.values()):
        report["status"] = "BASELINE_FAILED"
        return report
    try:
        compile(mutated_source, str(ROOT / mutation.source_path), "exec")
    except (SyntaxError, ValueError, TypeError):
        report["status"] = "COMPILE_ERROR"
        return report
    try:
        namespace = _load_source(mutated_source, mutation.source_path)
    except Exception as exc:
        report["status"] = "CRASHED"
        report["exception"] = type(exc).__name__
        return report
    mutant_probes = {
        name: _probe(namespace, name, probe_runner, copy.deepcopy(expectations[name]))
        for name in names
    }
    report["observations"]["mutant"] = mutant_probes
    if any(value["state"] == "CRASHED" for value in mutant_probes.values()):
        report["status"] = "CRASHED"
    elif any(value["state"] == "INVALID_OUTPUT" for value in mutant_probes.values()):
        report["status"] = "INVALID_OUTPUT"
    elif not mutant_probes[mutation.positive_control]["matched"]:
        report["status"] = "POSITIVE_CONTROL_FAILED"
    elif mutant_probes[mutation.adverse_test]["matched"]:
        report["status"] = "SURVIVED"
    else:
        report["status"] = "KILLED"
    return report


# Each tuple targets one named failure mode. Multi-site changes model one
# weakened rule where schema/cardinality/coverage guards otherwise overlap.
# No mutation writes these changes back to the consumer source.
SOURCE_PATH = "tools/guarantee_preservation.py"
COVERAGE = (
    '        require(len(depends_on) == len(set(depends_on))\n'
    '                and set(depends_on) == set(dependencies), "mandatory_dependency_coverage")'
)
SUBSET_COVERAGE = (
    '        require(len(depends_on) == len(set(depends_on))\n'
    '                and set(depends_on).issubset(set(dependencies)), "mandatory_dependency_coverage")'
)
OBSERVED_COVERAGE = '        require(set(observed) == set(dependencies), "missing_dependency_evidence")'
SUBSET_OBSERVED = '        require(set(observed).issubset(set(dependencies)), "missing_dependency_evidence")'
BASIS_ACCEPTANCE = (
    '    require(acceptance.get("status") == "ACCEPTED_BOUNDED"\n'
    '            and isinstance(acceptance.get("acceptance_ref"), str)\n'
    '            and bool(acceptance["acceptance_ref"].strip()), "basis_not_separately_accepted")'
)

MUTATIONS = (
    Mutation(
        "context-binding-bypass", SOURCE_PATH,
        (Replacement(
            '        require(envelope["context"] == policy.get("context"), "context_binding_mismatch")',
            '        require(True, "context_binding_mismatch")',
        ),),
        "test_context_binding_mismatch", "test_prf_positive_control",
    ),
    Mutation(
        "vacuous-empty-dependencies", SOURCE_PATH,
        (
            Replacement(
                '        validate_schema(envelope)',
                '        if envelope.get("depends_on"):\n            validate_schema(envelope)',
            ),
            Replacement(
                '        require(bool(depends_on), "empty_dependencies")',
                '        require(True, "empty_dependencies")',
            ),
            Replacement(COVERAGE, SUBSET_COVERAGE),
            Replacement(OBSERVED_COVERAGE, SUBSET_OBSERVED),
            Replacement('        for name in sorted(dependencies):', '        for name in sorted(observed):'),
        ),
        "test_empty_dependencies_fail_closed", "test_prf_positive_control",
    ),
    Mutation(
        "unaccepted-basis-acceptance", SOURCE_PATH,
        (Replacement(BASIS_ACCEPTANCE, '    require(True, "basis_not_separately_accepted")'),),
        "test_unaccepted_dependency_basis", "test_prf_positive_control",
    ),
    Mutation(
        "conflicting-witnesses-ignored", SOURCE_PATH,
        (
            Replacement(
                '            require(len({w["outcome"] for w in witnesses}) == 1, "conflicting_evidence")',
                '            require(True, "conflicting_evidence")',
            ),
            Replacement(
                '                require(witness == expected, "check_evidence_mismatch")',
                '                require(witness == expected or len({w["outcome"] for w in witnesses}) > 1, "check_evidence_mismatch")',
            ),
        ),
        "test_conflicting_evidence", "test_prf_positive_control",
    ),
    Mutation(
        "native-grade-shortcuts-transfer", SOURCE_PATH,
        (Replacement(
            '        if any(check["outcome"] == "FALSE" for check in resolved):',
            '        if any(check["outcome"] == "FALSE" for check in resolved) and envelope["native"]["evidence_grade"]["value"] != "AUTHENTICATED_REPORT":',
        ),),
        "test_native_grade_is_not_transfer_verdict", "test_kit_positive_control",
    ),
    Mutation(
        "dependency-digest-bypass", SOURCE_PATH,
        (Replacement(
            '        require(envelope["depends_on_digest"] == digest(depends_on), "dependency_digest_mismatch")',
            '        require(True, "dependency_digest_mismatch")',
        ),),
        "test_dependency_digest_binding", "test_prf_positive_control",
    ),
    Mutation(
        "omitted-required-false-relation", SOURCE_PATH,
        (
            Replacement(COVERAGE, SUBSET_COVERAGE),
            Replacement(OBSERVED_COVERAGE, SUBSET_OBSERVED),
            Replacement('        for name in sorted(dependencies):', '        for name in sorted(observed):'),
        ),
        "test_omitted_required_relation_fail_closed", "test_prf_positive_control",
    ),
)


def prepare_probes():
    try:
        from tools.guarantee_preservation import digest
        from tools.validate_guarantee_preservation import prepare
    except ModuleNotFoundError:
        from guarantee_preservation import digest
        from validate_guarantee_preservation import prepare

    positive = prepare("prf-price_preserving")
    kit_positive = prepare("kit-c2")
    probes = {
        "test_prf_positive_control": (*copy.deepcopy(positive[:3]), "PRESERVED"),
        "test_kit_positive_control": (*copy.deepcopy(kit_positive[:3]), "PRESERVED"),
    }

    def put(name, inputs, expected):
        probes[name] = (*copy.deepcopy(inputs[:3]), expected)

    def rebind_basis(envelope, policy, basis):
        basis_digest = digest(basis)
        policy["accepted_basis_digest"] = basis_digest
        envelope["dependency_basis"] = {"id": basis["id"], "digest": basis_digest}

    envelope, policy, basis = copy.deepcopy(positive[:3])
    policy["context"]["subject"] = "sha256:" + "0" * 64
    basis["context"] = copy.deepcopy(policy["context"])
    rebind_basis(envelope, policy, basis)
    put("test_context_binding_mismatch", (envelope, policy, basis), "UNVERIFIABLE")

    envelope, policy, basis = copy.deepcopy(positive[:3])
    envelope["depends_on"] = []
    envelope["depends_on_digest"] = digest([])
    envelope["checks"] = []
    put("test_empty_dependencies_fail_closed", (envelope, policy, basis), "UNVERIFIABLE")

    envelope, policy, basis = copy.deepcopy(positive[:3])
    basis["acceptance"]["status"] = "DECLARED_ONLY"
    rebind_basis(envelope, policy, basis)
    put("test_unaccepted_dependency_basis", (envelope, policy, basis), "UNVERIFIABLE")

    envelope, policy, basis = copy.deepcopy(positive[:3])
    conflicting = copy.deepcopy(envelope["checks"][-1])
    conflicting["outcome"] = "FALSE"
    conflicting["establishes"] = []
    envelope["checks"].append(conflicting)
    put("test_conflicting_evidence", (envelope, policy, basis), "UNVERIFIABLE")

    put(
        "test_native_grade_is_not_transfer_verdict",
        prepare("kit-M9-grade-signature-guard-removed"), "VIOLATED",
    )

    envelope, policy, basis = copy.deepcopy(positive[:3])
    envelope["depends_on_digest"] = "sha256:" + "0" * 64
    put("test_dependency_digest_binding", (envelope, policy, basis), "UNVERIFIABLE")

    envelope, policy, basis = copy.deepcopy(prepare("prf-fixed_reward_substitution")[:3])
    # The withheld FALSE is the economic relation, not a merely descriptive ref.
    omitted = "award_settlement_relation"
    envelope["depends_on"] = [name for name in envelope["depends_on"] if name != omitted]
    envelope["depends_on_digest"] = digest(envelope["depends_on"])
    envelope["checks"] = [check for check in envelope["checks"] if check["dependency_id"] != omitted]
    put("test_omitted_required_relation_fail_closed", (envelope, policy, basis), "UNVERIFIABLE")
    return probes


def probe_expectations(probes):
    try:
        from tools.guarantee_preservation import digest
    except ModuleNotFoundError:
        from guarantee_preservation import digest
    return {
        name: {
            "outcome": expected,
            "native": copy.deepcopy(envelope["native"]),
            "context": copy.deepcopy(policy["context"]),
            "policy_digest": digest(policy),
            "observation_bindings": {
                key: copy.deepcopy(envelope.get(key)) for key in OBSERVATION_BINDING_KEYS
            },
            "envelope_digest": digest(envelope),
            "evidence_digests": [
                {"ref": item.get("ref"), "digest": item.get("digest")}
                for item in envelope["evidence"]
            ],
            "guarantee": policy["context"]["guarantee_id"] if expected == "PRESERVED" else None,
            "establishes": [policy["context"]["guarantee_id"]] if expected == "PRESERVED" else [],
            "does_not_establish": copy.deepcopy(envelope["does_not_establish"]),
        }
        for name, (envelope, policy, basis, expected) in probes.items()
    }


def execute_probe(namespace, name, *, probes=None):
    try:
        from tools.guarantee_preservation_adapters import registry
    except ModuleNotFoundError:
        from guarantee_preservation_adapters import registry
    probes = prepare_probes() if probes is None else probes
    envelope, policy, basis, _ = copy.deepcopy(probes[name])
    return namespace["consume"](
        envelope, policy=policy, accepted_basis=basis, registry=registry(),
    )


REQUIRED_MUTATION_IDS = frozenset({
    "context-binding-bypass", "vacuous-empty-dependencies",
    "unaccepted-basis-acceptance", "conflicting-witnesses-ignored",
    "native-grade-shortcuts-transfer", "dependency-digest-bypass",
    "omitted-required-false-relation",
})


def run_mutations():
    if (len(MUTATIONS) != len(REQUIRED_MUTATION_IDS)
            or {mutation.name for mutation in MUTATIONS} != REQUIRED_MUTATION_IDS):
        raise MutationValidationError("required_mutation_coverage_changed")
    source = (ROOT / SOURCE_PATH).read_text(encoding="utf-8")
    probes = prepare_probes()
    expectations = probe_expectations(probes)
    records = [
        run_mutation(
            mutation, source_text=source,
            probe_runner=lambda namespace, name: execute_probe(namespace, name, probes=probes),
            expectations=expectations,
        )
        for mutation in MUTATIONS
    ]
    killed = sum(record["status"] == "KILLED" for record in records)
    return {
        "profile_id": "guarantee-preservation-v0",
        "status": "PASS" if killed == len(MUTATIONS) else "FAIL",
        "required_mutants": len(MUTATIONS),
        "killed": killed,
        "not_killed": len(MUTATIONS) - killed,
        "mutants": records,
        "scope": "named own-consumer source mutations compiled in memory; no upstream execution",
    }


class MutationValidationError(ValueError):
    pass


def validate_mutations():
    report = run_mutations()
    if report["status"] != "PASS":
        failed = ", ".join(
            f'{record["id"]}:{record["status"]}'
            for record in report["mutants"] if record["status"] != "KILLED"
        )
        raise MutationValidationError("mutation_controls_not_killed:" + failed)
    return report


def main():
    try:
        report = run_mutations()
    except (OSError, KeyError, TypeError, ValueError, ImportError) as exc:
        print(json.dumps({"status": "FAIL", "killed": 0, "reason": type(exc).__name__}, sort_keys=True))
        return 1
    print(json.dumps(report, sort_keys=True, indent=2, allow_nan=False))
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
