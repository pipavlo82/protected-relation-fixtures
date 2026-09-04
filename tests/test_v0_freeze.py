from __future__ import annotations

import hashlib
import json
from pathlib import Path, PurePosixPath
import shutil
import subprocess
import tempfile
import unittest

from tools.validate_v0_freeze import (
    FIRST_RUN_SHA256,
    FREEZE_RECORD_PATH,
    INVENTORY_PATH,
    NEGATIVE_CONTROLS_SHA256,
    REQUIRED_ARTIFACTS,
    SOURCE_COMMIT,
    FreezeViolation,
    derive_introduction_commit,
    validate_git_source_binding,
    validate_v0_freeze,
)


ROOT = Path(__file__).resolve().parents[1]


class V0FreezeTests(unittest.TestCase):
    def _git(self, root: Path, *arguments: str) -> str:
        process = subprocess.run(
            ["git", *arguments],
            cwd=root,
            check=True,
            capture_output=True,
            text=True,
        )
        return process.stdout.strip()

    def _write(self, root: Path, relative: str, content: str) -> None:
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8", newline="\n")

    def _commit(self, root: Path, message: str) -> str:
        self._git(root, "add", "--all")
        self._git(root, "commit", "-m", message)
        return self._git(root, "rev-parse", "HEAD")

    def _source_repository(self, root: Path) -> tuple[str, str]:
        self._git(root, "init", "-b", "main")
        self._git(root, "config", "user.name", "Freeze Test")
        self._git(root, "config", "user.email", "freeze-test@example.invalid")
        self._write(root, "frozen.txt", "source bytes\n")
        source = self._commit(root, "source")
        source_tree = self._git(root, "rev-parse", f"{source}^{{tree}}")
        return source, source_tree

    def _introduce_freeze(self, root: Path) -> str:
        self._write(root, FREEZE_RECORD_PATH.as_posix(), "freeze record\n")
        self._write(root, INVENTORY_PATH.as_posix(), "inventory\n")
        return self._commit(root, "introduce freeze")

    def _copy_freeze(self, destination: Path) -> Path:
        for relative in REQUIRED_ARTIFACTS:
            source = ROOT / Path(*PurePosixPath(relative).parts)
            target = destination / Path(*PurePosixPath(relative).parts)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)
        for relative in (FREEZE_RECORD_PATH, INVENTORY_PATH):
            source = ROOT / relative
            target = destination / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)
        return destination

    def _workspace(self, directory: str) -> Path:
        return self._copy_freeze(Path(directory))

    def _mutate_one_byte(self, root: Path, relative: str) -> None:
        path = root / relative
        raw = path.read_bytes()
        replacement = b"X" if raw[0:1] != b"X" else b"Y"
        path.write_bytes(replacement + raw[1:])

    def _write_json(self, path: Path, value: object) -> None:
        path.write_text(
            json.dumps(value, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
            newline="\n",
        )

    def _refresh_inventory_entry_and_pin(self, root: Path, relative: str) -> None:
        inventory_path = root / INVENTORY_PATH
        inventory = json.loads(inventory_path.read_text(encoding="utf-8"))
        artifact = root / relative
        for entry in inventory["entries"]:
            if entry["path"] == relative:
                raw = artifact.read_bytes()
                entry["byte_length"] = len(raw)
                entry["sha256"] = hashlib.sha256(raw).hexdigest()
                break
        else:
            self.fail(f"missing inventory entry for {relative}")
        self._write_json(inventory_path, inventory)
        record_path = root / FREEZE_RECORD_PATH
        record = json.loads(record_path.read_text(encoding="utf-8"))
        record["inventory"]["sha256"] = hashlib.sha256(inventory_path.read_bytes()).hexdigest()
        self._write_json(record_path, record)

    def _requires_violation(self, root: Path, pattern: str) -> None:
        with self.assertRaisesRegex(FreezeViolation, pattern):
            validate_v0_freeze(root, run_semantic_checks=False, check_git=False)

    def test_canonical_freeze_closure_validates(self) -> None:
        report = validate_v0_freeze(ROOT, run_semantic_checks=False, check_git=False)
        self.assertEqual(report["artifacts"], len(REQUIRED_ARTIFACTS))
        self.assertEqual(report["relation_axes"], 5)
        self.assertEqual(report["witnesses"], 8)
        self.assertEqual(report["independent_review"], "REPRODUCED")

    def test_one_byte_fixture_mutation_is_killed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self._workspace(directory)
            self._mutate_one_byte(root, "corpus/v0/cases/prf-001.json")
            self._requires_violation(root, "SHA-256 mismatch")

    def test_challenge_mutation_is_killed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self._workspace(directory)
            self._mutate_one_byte(root, "corpus/v0/challenge/cases/prf-001.json")
            self._requires_violation(root, "SHA-256 mismatch")

    def test_oracle_mutation_is_killed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self._workspace(directory)
            self._mutate_one_byte(root, "corpus/v0/oracle/expected-results.json")
            self._requires_violation(root, "SHA-256 mismatch")

    def test_manifest_mutation_is_killed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self._workspace(directory)
            self._mutate_one_byte(root, "corpus/v0/manifest.json")
            self._requires_violation(root, "SHA-256 mismatch")

    def test_fixture_schema_mutation_is_killed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self._workspace(directory)
            self._mutate_one_byte(root, "spec/fixture-schema.v0.json")
            self._requires_violation(root, "SHA-256 mismatch")

    def test_discrimination_suite_mutation_is_killed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self._workspace(directory)
            self._mutate_one_byte(root, "conformance/relation-discrimination-v0/suite.json")
            self._requires_violation(root, "SHA-256 mismatch")

    def test_first_run_review_mutation_is_killed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self._workspace(directory)
            self.assertEqual(
                hashlib.sha256((root / "review/relation-discrimination-independent-first-run.json").read_bytes()).hexdigest(),
                FIRST_RUN_SHA256,
            )
            self._mutate_one_byte(root, "review/relation-discrimination-independent-first-run.json")
            self._requires_violation(root, "SHA-256 mismatch")

    def test_negative_control_review_mutation_is_killed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self._workspace(directory)
            self.assertEqual(
                hashlib.sha256((root / "review/relation-discrimination-independent-negative-controls.json").read_bytes()).hexdigest(),
                NEGATIVE_CONTROLS_SHA256,
            )
            self._mutate_one_byte(root, "review/relation-discrimination-independent-negative-controls.json")
            self._requires_violation(root, "SHA-256 mismatch")

    def test_inventory_digest_mutation_is_killed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self._workspace(directory)
            record_path = root / FREEZE_RECORD_PATH
            record = json.loads(record_path.read_text(encoding="utf-8"))
            record["inventory"]["sha256"] = "0" * 64
            self._write_json(record_path, record)
            self._requires_violation(root, "inventory digest mismatch")

    def test_undeclared_closed_universe_file_is_killed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self._workspace(directory)
            (root / "corpus/v0/cases/undeclared.json").write_text("{}\n", encoding="utf-8", newline="\n")
            self._requires_violation(root, "closed universe mismatch")

    def test_missing_frozen_artifact_is_killed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self._workspace(directory)
            (root / "spec/outcome-model.md").unlink()
            self._requires_violation(root, "missing frozen artifact")

    def test_crlf_is_killed_even_with_refreshed_digest(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self._workspace(directory)
            relative = "docs/corpus-contract-v0.md"
            path = root / relative
            path.write_bytes(path.read_bytes().replace(b"\n", b"\r\n"))
            self._refresh_inventory_entry_and_pin(root, relative)
            self._requires_violation(root, "CR/CRLF forbidden")

    def test_authority_boundary_upgrade_is_killed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self._workspace(directory)
            record_path = root / FREEZE_RECORD_PATH
            record = json.loads(record_path.read_text(encoding="utf-8"))
            record["authority_boundary"]["remaining_boundary"] = "Objective semantic truth established."
            self._write_json(record_path, record)
            self._requires_violation(root, "remaining boundary changed")

    def test_unknown_freeze_record_field_is_killed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self._workspace(directory)
            record_path = root / FREEZE_RECORD_PATH
            record = json.loads(record_path.read_text(encoding="utf-8"))
            record["unsupported_upgrade"] = True
            self._write_json(record_path, record)
            self._requires_violation(root, "freeze-record field set mismatch")

    def test_introduction_commit_with_wrong_direct_parent_is_killed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source, source_tree = self._source_repository(root)
            self._write(root, "intermediate.txt", "intermediate\n")
            self._commit(root, "intermediate")
            self._introduce_freeze(root)
            with self.assertRaisesRegex(FreezeViolation, "FREEZE_INTRODUCTION_PARENT_MISMATCH"):
                validate_git_source_binding(
                    root,
                    source_commit=source,
                    source_tree=source_tree,
                    required_artifacts={"frozen.txt"},
                )

    def test_introduction_commit_with_multiple_parents_is_killed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source, source_tree = self._source_repository(root)
            self._git(root, "switch", "-c", "side")
            self._write(root, "side.txt", "side\n")
            self._commit(root, "side")
            self._git(root, "switch", "main")
            self._git(root, "merge", "--no-ff", "--no-commit", "side")
            introduction = self._introduce_freeze(root)
            with self.assertRaisesRegex(FreezeViolation, "FREEZE_INTRODUCTION_PARENT_COUNT_MISMATCH:2"):
                validate_git_source_binding(
                    root,
                    source_commit=source,
                    source_tree=source_tree,
                    required_artifacts={"frozen.txt"},
                    introduction_commit=introduction,
                )

    def test_freeze_record_drift_after_introduction_is_killed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source, source_tree = self._source_repository(root)
            introduction = self._introduce_freeze(root)
            self._write(root, FREEZE_RECORD_PATH.as_posix(), "changed freeze record\n")
            with self.assertRaisesRegex(FreezeViolation, "FROZEN_ARTIFACT_DRIFT_AFTER_INTRODUCTION.*freeze-record.json"):
                validate_git_source_binding(
                    root,
                    source_commit=source,
                    source_tree=source_tree,
                    required_artifacts={"frozen.txt"},
                    introduction_commit=introduction,
                )

    def test_inventory_drift_after_introduction_is_killed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source, source_tree = self._source_repository(root)
            introduction = self._introduce_freeze(root)
            self._write(root, INVENTORY_PATH.as_posix(), "changed inventory\n")
            with self.assertRaisesRegex(FreezeViolation, "FROZEN_ARTIFACT_DRIFT_AFTER_INTRODUCTION.*sha256-inventory.json"):
                validate_git_source_binding(
                    root,
                    source_commit=source,
                    source_tree=source_tree,
                    required_artifacts={"frozen.txt"},
                    introduction_commit=introduction,
                )

    def test_coherent_repin_cannot_rewrite_frozen_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source, source_tree = self._source_repository(root)
            introduction = self._introduce_freeze(root)
            self._write(root, "frozen.txt", "rewritten frozen bytes\n")
            self._write(root, INVENTORY_PATH.as_posix(), "coherently repinned inventory\n")
            self._write(root, FREEZE_RECORD_PATH.as_posix(), "coherently repinned record\n")
            with self.assertRaisesRegex(
                FreezeViolation,
                "FROZEN_ARTIFACT_DRIFT_AFTER_INTRODUCTION:.*frozen.txt.*freeze-record.json.*sha256-inventory.json",
            ):
                validate_git_source_binding(
                    root,
                    source_commit=source,
                    source_tree=source_tree,
                    required_artifacts={"frozen.txt"},
                    introduction_commit=introduction,
                )

    def test_introduction_commit_absent_from_head_ancestry_is_killed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source, source_tree = self._source_repository(root)
            self._git(root, "switch", "-c", "freeze")
            introduction = self._introduce_freeze(root)
            self._git(root, "switch", "main")
            with self.assertRaisesRegex(FreezeViolation, "FREEZE_INTRODUCTION_NOT_IN_HEAD_ANCESTRY"):
                validate_git_source_binding(
                    root,
                    source_commit=source,
                    source_tree=source_tree,
                    required_artifacts={"frozen.txt"},
                    introduction_commit=introduction,
                )

    def test_current_introduction_is_derived_from_history(self) -> None:
        introduction = derive_introduction_commit(ROOT)
        self.assertEqual(
            self._git(ROOT, "show", "-s", "--format=%P", introduction),
            SOURCE_COMMIT,
        )
        self.assertEqual(validate_git_source_binding(ROOT), introduction)


if __name__ == "__main__":
    unittest.main()
