from __future__ import annotations

import hashlib
import os
from pathlib import Path
import subprocess
import unittest


ROOT = Path(__file__).resolve().parents[1]
LF_SOURCE = "conformance/award-actual-settlement-v0/sources.json"
CRLF_SOURCE = (
    "evidence/external-evaluators/v0/codex-gpt56-sol-repeated/"
    "payload/isolation-prompt-input.json"
)
BINARY_SOURCE = (
    "evidence/external-evaluators/v0/repeated-runs/"
    "payload/harness/__pycache__/common.cpython-312.pyc"
)
CAPTURE_LANES = ("first-runs", "repeated-runs", "codex-gpt56-sol-repeated")


def git_bytes(*arguments: str) -> bytes:
    """Read Git output without changing configuration, files, or the index."""
    environment = os.environ.copy()
    environment["GIT_CONFIG_NOSYSTEM"] = "1"
    environment["GIT_CONFIG_GLOBAL"] = os.devnull
    completed = subprocess.run(
        [
            "git",
            "-c", "core.autocrlf=true",
            "-c", "core.eol=crlf",
            "-c", f"core.attributesfile={os.devnull}",
            *arguments,
        ],
        cwd=ROOT,
        env=environment,
        capture_output=True,
        timeout=30,
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError(
            f"Git read failed ({completed.returncode}): "
            f"{completed.stderr.decode('utf-8', errors='replace').strip()}"
        )
    return completed.stdout


class GitAttributesTests(unittest.TestCase):
    """Exercise checkout conversion on committed blobs under Windows settings.

    Synthetic attributed paths select the rules; no fixture files or repository
    are created. Failure messages expose hashes, never captured payload content.
    """

    @classmethod
    def setUpClass(cls) -> None:
        cls.lf = git_bytes("show", f"HEAD:{LF_SOURCE}")
        cls.crlf = git_bytes("show", f"HEAD:{CRLF_SOURCE}")
        cls.binary = git_bytes("show", f"HEAD:{BINARY_SOURCE}")
        if not cls.lf or b"\n" not in cls.lf or b"\r" in cls.lf:
            raise RuntimeError("LF representative no longer has exclusively LF text")
        if b"\r\n" not in cls.crlf or b"\x00" in cls.crlf:
            raise RuntimeError("CRLF representative no longer contains captured CRLF text")
        if b"\x00" not in cls.binary:
            raise RuntimeError("Binary representative no longer contains NUL bytes")

    def filtered(self, attributed_path: str, source: str) -> bytes:
        return git_bytes(
            "cat-file", "--filters", f"--path={attributed_path}", f"HEAD:{source}",
        )

    def assert_exact_bytes(self, actual: bytes, expected: bytes, path: str) -> None:
        self.assertTrue(
            actual == expected,
            f"Byte drift at {path}; "
            f"expected={len(expected)} bytes/{hashlib.sha256(expected).hexdigest()}, "
            f"actual={len(actual)} bytes/{hashlib.sha256(actual).hexdigest()}",
        )

    def test_ordinary_technical_formats_checkout_as_lf(self) -> None:
        paths = [
            f"notes/attribute-regression/example.{extension}"
            for extension in ("md", "txt", "json", "yml", "yaml", "py", "cff")
        ]
        for path in paths:
            with self.subTest(path=path):
                self.assert_exact_bytes(self.filtered(path, LF_SOURCE), self.lf, path)

    def test_captured_ascii_bin_and_text_preserve_lf_and_crlf_across_lanes(self) -> None:
        for lane in CAPTURE_LANES:
            for extension in ("json", "txt", "jsonl", "toml", "bin"):
                path = (
                    f"evidence/external-evaluators/v0/{lane}/"
                    f"payload/attribute-regression/probe.{extension}"
                )
                for source, raw in ((LF_SOURCE, self.lf), (CRLF_SOURCE, self.crlf)):
                    with self.subTest(lane=lane, extension=extension, source=source):
                        self.assert_exact_bytes(self.filtered(path, source), raw, path)

    def test_captured_binary_preserves_all_bytes_across_lanes(self) -> None:
        for lane in CAPTURE_LANES:
            path = (
                f"evidence/external-evaluators/v0/{lane}/"
                "payload/attribute-regression/probe.bin"
            )
            with self.subTest(lane=lane):
                self.assert_exact_bytes(self.filtered(path, BINARY_SOURCE), self.binary, path)

    def test_trustless_raw_http_headers_preserve_exact_crlf(self) -> None:
        path = "evidence/external-systems/trustless-ai/v0/live/gateway-verify.headers.txt"
        self.assert_exact_bytes(self.filtered(path, CRLF_SOURCE), self.crlf, path)

    def test_outside_binary_and_unspecified_text_keep_default_git_behavior(self) -> None:
        binary_path = "notes/attribute-regression/probe.bin"
        self.assert_exact_bytes(
            self.filtered(binary_path, BINARY_SOURCE), self.binary, binary_path,
        )
        ordinary_path = "notes/attribute-regression/probe.unclassified"
        expected_crlf = self.lf.replace(b"\n", b"\r\n")
        self.assert_exact_bytes(
            self.filtered(ordinary_path, LF_SOURCE), expected_crlf, ordinary_path,
        )


if __name__ == "__main__":
    unittest.main()
