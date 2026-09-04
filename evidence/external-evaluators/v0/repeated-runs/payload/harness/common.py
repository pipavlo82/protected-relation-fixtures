from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


ROOT = Path(r"D:\prf-experiments\repeated-runs-v0")
REPO = Path(r"C:\Users\msi\Documents\Codex\2026-08-25\we-are-closing-the-erc-8309\protected-relation-fixtures")

STARTING_MAIN = "5fdd96a0ca9df399bb946fdba089992b8b3ad4db"
V0_COMMIT = "98ccba804c725777e155ad2f1a07bae49754376b"
V0_TREE = "c2449cb3a52e60c4f93e3c8a3a35c086c47f2d63"
ADAPTER_COMMIT = "cf39a37d66222522368e719e3910c27a3eab31dd"
EVALUATOR_OUTPUT_SCHEMA_SHA256 = "60c3c89bf2ae7d5d406c4449da5e3de728cd37c9ab3749038b7da30193a33fff"
RESPONSE_SCHEMA_SHA256 = "a8557965c090cb8e6d1a4dbc0e2b7cd44832e1b16dd2021d63a92729aaab0a7a"

CHALLENGE_IDS = tuple(f"prf-{index:03d}" for index in range(1, 7))
RUN_INDICES = tuple(range(1, 11))
MODEL_KEYS = (
    "qwen2.5-3b-instruct",
    "qwen2.5-coder-7b",
    "llama3.1-8b",
)
MODEL_SPECS: dict[str, dict[str, str]] = {
    "qwen2.5-3b-instruct": {
        "model": "qwen2.5:3b-instruct",
        "model_id": "357c53fb659c",
        "payload_sha256": "5ee4f07cdb9beadbbb293e85803c569b01bd37ed059d2715faa7bb405f31caa6",
        "format": "GGUF",
        "quantization": "Q4_K_M",
    },
    "qwen2.5-coder-7b": {
        "model": "qwen2.5-coder:7b",
        "model_id": "dae161e27b0e",
        "payload_sha256": "60e05f2100071479f596b964f89f510f057ce397ea22f2833a0cfe029bfc2463",
        "format": "GGUF",
        "quantization": "Q4_K_M",
    },
    "llama3.1-8b": {
        "model": "llama3.1:8b",
        "model_id": "46e0c10c039e",
        "payload_sha256": "667b0c1932bc6ffc593ed1d03f895bf2dc8dc6df21db3042284a6f4416b06a29",
        "format": "GGUF",
        "quantization": "Q4_K_M",
    },
}

INSTRUCTION = """You are an external Protected Relation Fixtures semantic evaluator.

Apply ONLY the protected relation profile supplied by the request to the supplied before/after state.

Do not guess benchmark correctness and do not invent a different protected relation.

Return PRESERVED only if preservation is justified under the supplied relation.
Return VIOLATED only if violation is justified.
If the available semantic information is insufficient, return UNVERIFIABLE.

Return only one JSON object with exactly these two fields and no others:
{"outcome":"PRESERVED | VIOLATED | UNVERIFIABLE","reason_detail":"string"}

The outcome value must be exactly one of PRESERVED, VIOLATED, or UNVERIFIABLE. The reason_detail value must be a JSON string.

Validated blind request:
"""


def canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def digest_value(value: Any) -> str:
    return hashlib.sha256(canonical_json_bytes(value)).hexdigest()


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def prompt_bytes(request_bytes_without_lf: bytes) -> bytes:
    return INSTRUCTION.encode("utf-8") + request_bytes_without_lf + b"\n"


def observation_root(model_key: str, challenge_id: str, run_index: int) -> Path:
    return ROOT / model_key / challenge_id / f"run-{run_index:02d}"
