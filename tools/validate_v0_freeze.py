from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import subprocess
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
RELEASE_ROOT = Path("releases/v0")
FREEZE_RECORD_PATH = RELEASE_ROOT / "freeze-record.json"
INVENTORY_PATH = RELEASE_ROOT / "sha256-inventory.json"
ENVIRONMENT_PATH = RELEASE_ROOT / "environment.json"

SOURCE_COMMIT = "46b34ac17d4fc67b5d95aa68835202b83040b4cf"
SOURCE_TREE = "2033469318234335aa1c5f5d4729f4ce5c1fa166"
INDEPENDENT_IMPLEMENTATION_SHA256 = (
    "1d8adf8e502484ab462f06cd6bd2c3eb2ca1d76bf61cc849b9f9c093c3dd4cc6"
)
FIRST_RUN_SHA256 = "b918fd86b3ebd68b22dd92241e03194162dfab04effc37bca0d69550b2674510"
NEGATIVE_CONTROLS_SHA256 = (
    "edd7daf99df34600ce9ac29d6a610405eec2a414e2524c45fb0c6b93fb5bd5e1"
)

FREEZE_CLAIM = (
    "Exact benchmark artifacts, declared semantic contracts, validation machinery, "
    "discrimination witnesses, and second-implementation reproduction evidence are "
    "bound to an immutable repository state and exact-byte inventory."
)
SECOND_REVIEW_CLAIM = (
    "Two separately implemented evaluators reproduce the declared "
    "relation-discrimination contract over the exact synthetic witness suite."
)
REMAINING_BOUNDARY = (
    "The synthetic witness construction, alias maps, scope declarations, and "
    "completeness markers remain declared benchmark inputs. Agreement between two "
    "implementations does not independently establish that those declarations "
    "correctly model every external domain."
)


class FreezeViolation(ValueError):
    """A fail-closed v0 freeze-closure violation."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise FreezeViolation(message)


def _fixture_paths(root: str) -> dict[str, str]:
    return {f"{root}/prf-{index:03d}.json": "" for index in range(1, 7)}


REQUIRED_ARTIFACTS: dict[str, str] = {
    ".gitattributes": "byte-policy",
    ".github/workflows/validate.yml": "validation-environment",
    "requirements-dev.txt": "validation-environment",
    "docs/corpus-contract-v0.md": "semantic-contract",
    "spec/fixture-schema.v0.json": "fixture-schema",
    "spec/outcome-model.md": "semantic-contract",
    "spec/projection-model.md": "semantic-contract",
    "spec/protected-relation-model.md": "semantic-contract",
    "spec/relation-discrimination-v0.md": "discrimination-contract",
    **{path: "seed-case" for path in _fixture_paths("corpus/v0/cases")},
    **{path: "blind-challenge" for path in _fixture_paths("corpus/v0/challenge/cases")},
    "corpus/v0/manifest.json": "seed-manifest",
    "corpus/v0/oracle/expected-results.json": "seed-oracle",
    "conformance/relation-discrimination-v0/suite.json": "discrimination-suite",
    "tools/corpus_contract.py": "seed-evaluator",
    "tools/derive_challenge_views.py": "challenge-deriver",
    "tools/validate_manifest.py": "seed-validator",
    "tools/validate_seed_corpus.py": "seed-validator",
    "tools/relation_discrimination.py": "discrimination-evaluator",
    "tools/validate_relation_discrimination.py": "discrimination-validator",
    "tests/test_manifest_and_seed_corpus.py": "seed-tests",
    "tests/test_relation_discrimination.py": "discrimination-tests",
    "review/relation_discrimination_independent.py": "independent-review-evaluator",
    "review/relation-discrimination-independent-first-run.json": "independent-review-result",
    "review/relation-discrimination-independent-negative-controls.json": (
        "independent-review-negative-controls"
    ),
    "review/relation-discrimination-v0-independent-review.md": "independent-review-record",
    "releases/v0/README.md": "freeze-documentation",
    "releases/v0/environment.json": "validation-environment",
    "tools/validate_v0_freeze.py": "freeze-validator",
    "tests/test_v0_freeze.py": "freeze-tests",
}

CLOSED_UNIVERSES: dict[str, set[str]] = {
    "corpus/v0/cases": {f"prf-{index:03d}.json" for index in range(1, 7)},
    "corpus/v0/challenge/cases": {f"prf-{index:03d}.json" for index in range(1, 7)},
    "corpus/v0/oracle": {"expected-results.json"},
    "conformance/relation-discrimination-v0": {"suite.json"},
    "review": {
        "relation_discrimination_independent.py",
        "relation-discrimination-independent-first-run.json",
        "relation-discrimination-independent-negative-controls.json",
        "relation-discrimination-v0-independent-review.md",
    },
    "releases/v0": {
        "README.md",
        "environment.json",
        "freeze-record.json",
        "sha256-inventory.json",
    },
}


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate_text_bytes(path: Path) -> bytes:
    raw = path.read_bytes()
    require(bool(raw), f"empty frozen text artifact: {path}")
    require(not raw.startswith(b"\xef\xbb\xbf"), f"UTF-8 BOM forbidden: {path}")
    require(b"\r" not in raw, f"CR/CRLF forbidden: {path}")
    require(b"\x00" not in raw, f"NUL forbidden: {path}")
    require(raw.endswith(b"\n"), f"missing final LF: {path}")
    require(not raw.endswith(b"\n\n"), f"more than one final LF: {path}")
    try:
        raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise FreezeViolation(f"invalid UTF-8: {path}: {exc}") from exc
    return raw


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        require(key not in result, f"duplicate JSON member: {key}")
        result[key] = value
    return result


def load_exact_json(path: Path) -> Any:
    raw = validate_text_bytes(path)
    try:
        return json.loads(raw.decode("utf-8"), object_pairs_hook=_unique_object)
    except json.JSONDecodeError as exc:
        raise FreezeViolation(f"invalid JSON at {path}: {exc}") from exc


def _validate_posix_relative(path: str) -> None:
    parsed = PurePosixPath(path)
    require(path == parsed.as_posix(), f"non-POSIX inventory path: {path}")
    require(not parsed.is_absolute(), f"absolute inventory path: {path}")
    require(".." not in parsed.parts, f"parent traversal in inventory path: {path}")


def validate_closed_universes(root: Path) -> None:
    for relative, expected in CLOSED_UNIVERSES.items():
        directory = root / relative
        require(directory.is_dir(), f"missing closed frozen directory: {relative}")
        actual = {path.name for path in directory.iterdir() if path.is_file()}
        require(actual == expected, f"closed universe mismatch for {relative}: {sorted(actual)}")
        require(
            all(not path.is_dir() for path in directory.iterdir()),
            f"nested directory in closed frozen universe: {relative}",
        )


def validate_inventory(root: Path, freeze_record: dict[str, Any]) -> tuple[int, int]:
    inventory_path = root / INVENTORY_PATH
    expected_digest = freeze_record.get("inventory", {}).get("sha256")
    require(isinstance(expected_digest, str), "missing freeze-record inventory digest")
    require(sha256_file(inventory_path) == expected_digest, "inventory digest mismatch")
    inventory = load_exact_json(inventory_path)
    require(
        set(inventory) == {"schema", "corpus_version", "entries"},
        "inventory field set mismatch",
    )
    require(inventory["schema"] == "protected-relation-fixtures-sha256-inventory.v0", "inventory schema mismatch")
    require(inventory["corpus_version"] == "v0", "inventory corpus version mismatch")
    entries = inventory["entries"]
    require(isinstance(entries, list), "inventory entries must be an array")
    paths = [entry.get("path") for entry in entries if isinstance(entry, dict)]
    require(len(paths) == len(entries), "inventory entry must be an object")
    require(paths == sorted(paths), "inventory paths are not lexicographically sorted")
    require(len(paths) == len(set(paths)), "duplicate inventory path")
    require(set(paths) == set(REQUIRED_ARTIFACTS), "required frozen artifact inventory mismatch")

    total_bytes = 0
    for entry in entries:
        require(set(entry) == {"path", "byte_length", "sha256", "role"}, "inventory entry field set mismatch")
        path = entry["path"]
        require(isinstance(path, str), "inventory path must be a string")
        _validate_posix_relative(path)
        require(entry["role"] == REQUIRED_ARTIFACTS[path], f"inventory role mismatch: {path}")
        require(
            isinstance(entry["byte_length"], int) and not isinstance(entry["byte_length"], bool),
            f"invalid byte length: {path}",
        )
        require(
            isinstance(entry["sha256"], str)
            and len(entry["sha256"]) == 64
            and all(character in "0123456789abcdef" for character in entry["sha256"]),
            f"invalid SHA-256: {path}",
        )
        artifact = root / Path(*PurePosixPath(path).parts)
        require(artifact.is_file(), f"missing frozen artifact: {path}")
        raw = artifact.read_bytes()
        require(len(raw) == entry["byte_length"], f"byte length mismatch: {path}")
        require(hashlib.sha256(raw).hexdigest() == entry["sha256"], f"SHA-256 mismatch: {path}")
        validate_text_bytes(artifact)
        total_bytes += len(raw)

    declared = freeze_record.get("inventory", {})
    require(declared.get("entry_count") == len(entries), "freeze-record inventory count mismatch")
    require(declared.get("byte_total") == total_bytes, "freeze-record inventory byte total mismatch")
    return len(entries), total_bytes


def validate_environment(root: Path) -> None:
    environment = load_exact_json(root / ENVIRONMENT_PATH)
    require(
        environment.get("schema") == "protected-relation-fixtures-validation-environment.v0",
        "environment schema mismatch",
    )
    require(environment.get("status") == "RECORDED_NOT_HERMETIC", "environment status mismatch")
    canonical = environment.get("canonical_ci")
    require(isinstance(canonical, dict), "missing canonical CI environment")
    require(canonical.get("python") == "3.12", "canonical Python version mismatch")
    require(canonical.get("dependencies") == {"jsonschema": "4.26.0"}, "dependency pin mismatch")
    require(
        (root / "requirements-dev.txt").read_text(encoding="utf-8") == "jsonschema==4.26.0\n",
        "requirements-dev dependency mismatch",
    )
    require(
        "Bit-for-bit runtime determinism is not claimed" in environment.get("determinism_boundary", ""),
        "environment determinism boundary missing",
    )


def validate_review_evidence(root: Path, freeze_record: dict[str, Any]) -> None:
    review = freeze_record.get("independent_review")
    require(isinstance(review, dict), "missing independent-review freeze binding")
    expected_hashes = {
        "independent_implementation_sha256": INDEPENDENT_IMPLEMENTATION_SHA256,
        "first_run_artifact_sha256": FIRST_RUN_SHA256,
        "negative_control_artifact_sha256": NEGATIVE_CONTROLS_SHA256,
    }
    for key, value in expected_hashes.items():
        require(review.get(key) == value, f"independent-review digest binding mismatch: {key}")
    require(review.get("verdict") == "REPRODUCED", "independent-review verdict mismatch")
    require(review.get("review_mode") == "NON_BLIND_SECOND_IMPLEMENTATION", "review mode mismatch")
    require(review.get("semantic_outcomes_matched") == 80, "independent outcome total mismatch")
    require(review.get("semantic_mismatches") == 0, "independent semantic mismatch count")
    require(review.get("negative_controls_passed") == 11, "independent negative-control total mismatch")

    first_run = load_exact_json(root / "review/relation-discrimination-independent-first-run.json")
    require(first_run.get("status") == "REPRODUCED", "first-run review verdict mismatch")
    require(first_run.get("review_mode") == "NON_BLIND_SECOND_IMPLEMENTATION", "first-run mode mismatch")
    require(first_run.get("candidate_implementation_imported") is False, "candidate evaluator imported")
    require(first_run.get("expected_matrix_matches") is True, "first-run matrix mismatch")
    require(first_run.get("policy_pair_witness_side_outcomes") == 80, "first-run outcome count mismatch")
    require(first_run.get("required_axes") == 5, "first-run required-axis count mismatch")
    require(first_run.get("separated_axes") == 5, "first-run separated-axis count mismatch")
    require(first_run.get("witnesses") == 8, "first-run witness count mismatch")

    negative = load_exact_json(root / "review/relation-discrimination-independent-negative-controls.json")
    require(negative.get("status") == "PASS", "review negative-control status mismatch")
    require(negative.get("passed") == 11 and negative.get("total") == 11, "review negative-control count mismatch")

    record_text = (root / "review/relation-discrimination-v0-independent-review.md").read_text(encoding="utf-8")
    normalized = " ".join(
        line.removeprefix("> ").strip() for line in record_text.splitlines()
    )
    require(SECOND_REVIEW_CLAIM in normalized, "second-review authority claim changed")
    require(REMAINING_BOUNDARY in normalized, "remaining authority boundary changed")


def validate_freeze_record(root: Path) -> dict[str, Any]:
    record = load_exact_json(root / FREEZE_RECORD_PATH)
    require(
        set(record)
        == {
            "schema",
            "corpus_version",
            "freeze_status",
            "source_repository",
            "source_binding",
            "freeze_commit_model",
            "inventory",
            "validation_environment",
            "validation_commands",
            "relation_discrimination",
            "independent_review",
            "authority_boundary",
            "versioning",
        },
        "freeze-record field set mismatch",
    )
    require(record["schema"] == "protected-relation-fixtures-freeze-record.v0", "freeze-record schema mismatch")
    require(record["corpus_version"] == "v0", "freeze-record corpus version mismatch")
    require(record["freeze_status"] == "FREEZE_CLOSURE_CANDIDATE", "freeze status mismatch")
    require(record["source_repository"] == "https://github.com/pipavlo82/protected-relation-fixtures", "source repository mismatch")
    source = record["source_binding"]
    require(set(source) == {"pre_freeze_commit", "git_tree"}, "source binding field set mismatch")
    require(source.get("pre_freeze_commit") == SOURCE_COMMIT, "source commit mismatch")
    require(source.get("git_tree") == SOURCE_TREE, "source tree mismatch")
    commit_model = record["freeze_commit_model"]
    require(
        set(commit_model)
        == {
            "mode",
            "bound_parent",
            "introduction_commit",
            "self_referential_commit_claim",
            "description",
        },
        "freeze commit model field set mismatch",
    )
    require(commit_model.get("mode") == "PARENT_BOUND_INTRODUCTION_COMMIT", "freeze commit model mismatch")
    require(commit_model.get("bound_parent") == SOURCE_COMMIT, "freeze commit parent binding mismatch")
    require(commit_model.get("introduction_commit") == "DERIVE_FROM_GIT_HISTORY", "freeze commit derivation mismatch")
    require(commit_model.get("self_referential_commit_claim") is False, "self-referential commit claim forbidden")
    inventory = record["inventory"]
    require(
        set(inventory) == {"path", "sha256", "entry_count", "byte_total", "self_reference_model"},
        "freeze inventory binding field set mismatch",
    )
    require(inventory.get("path") == INVENTORY_PATH.as_posix(), "inventory path mismatch")
    require(record["validation_environment"] == ENVIRONMENT_PATH.as_posix(), "environment path mismatch")
    require(
        record["validation_commands"]
        == [
            "python tools/validate_manifest.py",
            "python tools/validate_seed_corpus.py",
            "python tools/validate_relation_discrimination.py",
            "python tools/validate_v0_freeze.py",
            "python -m unittest discover -s tests -v",
            "python -O -m unittest discover -s tests -v",
            "git diff --check",
        ],
        "validation command set mismatch",
    )
    relation = record["relation_discrimination"]
    require(
        set(relation) == {"contract", "suite_sha256", "status", "required_axes", "separated_axes", "witnesses"},
        "relation-discrimination binding field set mismatch",
    )
    require(relation.get("contract") == "relation-discrimination-v0", "relation contract mismatch")
    require(
        relation.get("suite_sha256")
        == "acc7b82ac0c2f87e7c6c78e099482481bb72ca604f45d6f17f991834b5aaeb18",
        "relation suite digest mismatch",
    )
    require(relation.get("status") == "SEPARATED", "relation-discrimination status mismatch")
    require(relation.get("required_axes") == 5 and relation.get("separated_axes") == 5, "relation axis total mismatch")
    require(relation.get("witnesses") == 8, "relation witness total mismatch")
    review = record["independent_review"]
    require(review.get("reviewed_pr_head") == "b14d63e0d8f869c0b7aa0efdb1d2a0a23ed6dd68", "reviewed head mismatch")
    require(review.get("separated_axes") == 5, "independent separated-axis count mismatch")
    authority = record["authority_boundary"]
    require(authority.get("freeze_establishes") == FREEZE_CLAIM, "freeze authority claim changed")
    require(authority.get("second_review_claim") == SECOND_REVIEW_CLAIM, "second-review claim changed")
    require(authority.get("remaining_boundary") == REMAINING_BOUNDARY, "remaining boundary changed")
    require(
        authority.get("does_not_establish")
        == [
            "objective semantic truth for every external domain",
            "correctness of every real-world alias map",
            "correctness of every future scope declaration",
            "universal equivalence semantics",
            "correctness of external evaluators not covered by this release",
        ],
        "negative authority boundary changed",
    )
    versioning = record["versioning"]
    require(versioning.get("rewrite_frozen_v0_in_place") is False, "v0 rewrite prohibition missing")
    require(versioning.get("semantic_changes_require_successor") is True, "successor rule missing")
    require(versioning.get("metadata_corrections_are_append_only") is True, "append-only correction rule missing")
    require(versioning.get("future_fixture_additions_require_successor") is True, "future fixture rule missing")
    return record


def _git(
    root: Path,
    *arguments: str,
    check: bool = True,
    text: bool = True,
) -> subprocess.CompletedProcess[Any]:
    try:
        return subprocess.run(
            ["git", *arguments],
            cwd=root,
            check=check,
            capture_output=True,
            text=text,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        raise FreezeViolation(f"could not verify source Git binding: {exc}") from exc


def derive_introduction_commit(root: Path) -> str:
    history = _git(
        root,
        "log",
        "--diff-filter=A",
        "--format=%H",
        "HEAD",
        "--",
        FREEZE_RECORD_PATH.as_posix(),
    ).stdout
    commits = [line for line in history.splitlines() if line]
    require(
        len(commits) == 1,
        f"FREEZE_INTRODUCTION_COMMIT_COUNT_MISMATCH:{len(commits)}",
    )
    return commits[0]


def validate_git_source_binding(
    root: Path,
    *,
    source_commit: str = SOURCE_COMMIT,
    source_tree: str = SOURCE_TREE,
    required_artifacts: set[str] | None = None,
    introduction_commit: str | None = None,
    head: str = "HEAD",
) -> str:
    tree = _git(root, "rev-parse", f"{source_commit}^{{tree}}").stdout.strip()
    require(tree == source_tree, "source Git tree mismatch")

    introduction = introduction_commit or derive_introduction_commit(root)
    parent_line = _git(root, "show", "-s", "--format=%P", introduction).stdout.strip()
    parents = parent_line.split() if parent_line else []
    require(
        len(parents) == 1,
        f"FREEZE_INTRODUCTION_PARENT_COUNT_MISMATCH:{len(parents)}",
    )
    require(
        parents[0] == source_commit,
        f"FREEZE_INTRODUCTION_PARENT_MISMATCH:{parents[0]}",
    )

    introduction_ancestry = _git(
        root,
        "merge-base",
        "--is-ancestor",
        introduction,
        head,
        check=False,
    )
    require(
        introduction_ancestry.returncode == 0,
        "FREEZE_INTRODUCTION_NOT_IN_HEAD_ANCESTRY",
    )

    paths = set(REQUIRED_ARTIFACTS) if required_artifacts is None else set(required_artifacts)
    paths.update({FREEZE_RECORD_PATH.as_posix(), INVENTORY_PATH.as_posix()})
    drift: list[str] = []
    for relative in sorted(paths):
        current = root / Path(*PurePosixPath(relative).parts)
        if not current.is_file() or current.is_symlink():
            drift.append(relative)
            continue
        blob = _git(
            root,
            "show",
            f"{introduction}:{relative}",
            check=False,
            text=False,
        )
        if blob.returncode != 0 or current.read_bytes() != blob.stdout:
            drift.append(relative)
    require(
        not drift,
        "FROZEN_ARTIFACT_DRIFT_AFTER_INTRODUCTION:" + ",".join(drift),
    )
    return introduction


def run_semantic_validators(root: Path) -> None:
    commands = [
        ("tools/validate_manifest.py", "manifest validation: PASS"),
        ("tools/validate_seed_corpus.py", "seed corpus validation: PASS"),
        ("tools/validate_relation_discrimination.py", "relation discrimination: PASS (5/5 axes; 8 witnesses)"),
    ]
    environment = dict(os.environ)
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    for script, marker in commands:
        process = subprocess.run(
            [sys.executable, "-B", script],
            cwd=root,
            env=environment,
            check=False,
            capture_output=True,
            text=True,
        )
        require(process.returncode == 0, f"semantic validator failed: {script}: {process.stdout}{process.stderr}")
        require(marker in process.stdout, f"semantic validator result marker missing: {script}")


def validate_v0_freeze(
    root: Path = ROOT,
    *,
    run_semantic_checks: bool = True,
    check_git: bool = True,
) -> dict[str, Any]:
    root = root.resolve()
    record = validate_freeze_record(root)
    validate_closed_universes(root)
    count, byte_total = validate_inventory(root, record)
    validate_environment(root)
    validate_review_evidence(root, record)
    for relative in (FREEZE_RECORD_PATH, INVENTORY_PATH):
        validate_text_bytes(root / relative)
    if check_git:
        introduction = validate_git_source_binding(root)
    else:
        introduction = None
    if run_semantic_checks:
        run_semantic_validators(root)
    return {
        "artifacts": count,
        "byte_total": byte_total,
        "relation_axes": 5,
        "witnesses": 8,
        "independent_review": "REPRODUCED",
        "introduction_commit": introduction,
    }


def main() -> int:
    try:
        report = validate_v0_freeze()
    except FreezeViolation as exc:
        print(f"v0 freeze validation: FAIL: {exc}")
        return 1
    print(
        "v0 freeze validation: PASS "
        f"({report['artifacts']} artifacts; {report['byte_total']} bytes; "
        f"{report['relation_axes']}/5 axes; {report['witnesses']} witnesses; "
        f"second implementation {report['independent_review']})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
