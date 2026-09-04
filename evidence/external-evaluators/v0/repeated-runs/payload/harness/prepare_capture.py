from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys

from common import (
    ADAPTER_COMMIT,
    CHALLENGE_IDS,
    EVALUATOR_OUTPUT_SCHEMA_SHA256,
    MODEL_KEYS,
    MODEL_SPECS,
    REPO,
    RESPONSE_SCHEMA_SHA256,
    ROOT,
    STARTING_MAIN,
    V0_COMMIT,
    V0_TREE,
    canonical_json_bytes,
    digest_value,
    prompt_bytes,
    sha256_bytes,
    write_json,
)


sys.path.insert(0, str(REPO))
from adapters.v0.contract import (  # noqa: E402
    CHALLENGE_ROOT,
    assert_oracle_blind_request,
    build_request,
    validate_frozen_v0_request_binding,
)


SECRET_PATTERNS = {
    "github_token": re.compile(rb"(?i)(?:gh[pousr]_[A-Za-z0-9_]{30,}|github_pat_[A-Za-z0-9_]{30,})"),
    "bearer_header": re.compile(rb"(?i)authorization\s*:\s*bearer\s+[A-Za-z0-9._~+/=-]{12,}"),
    "private_key": re.compile(rb"-----BEGIN (?:RSA |EC |OPENSSH |PGP )?PRIVATE KEY-----"),
    "api_key": re.compile(rb"\bsk-[A-Za-z0-9_-]{20,}\b"),
}


def git(*args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=REPO, check=True, capture_output=True, text=True
    ).stdout.strip()


def main() -> int:
    if git("rev-parse", "HEAD") != STARTING_MAIN or git("rev-parse", "origin/main") != STARTING_MAIN:
        raise RuntimeError("canonical main drift")
    if git("rev-parse", "v0^{commit}") != V0_COMMIT or git("rev-parse", "v0^{tree}") != V0_TREE:
        raise RuntimeError("frozen v0 identity drift")
    if git("status", "--porcelain"):
        raise RuntimeError("repository worktree is not clean")

    list_process = subprocess.run(
        ["wsl.exe", "-d", "Ubuntu", "--", "/usr/local/bin/ollama", "list"],
        check=True,
        capture_output=True,
    )
    (ROOT / "metadata").mkdir(parents=True, exist_ok=True)
    (ROOT / "metadata/ollama-list.stdout.bin").write_bytes(list_process.stdout)
    (ROOT / "metadata/ollama-list.stderr.bin").write_bytes(list_process.stderr)
    list_text = list_process.stdout.decode("utf-8")

    identities = []
    leakage_checks = []
    for model_key in MODEL_KEYS:
        spec = MODEL_SPECS[model_key]
        match = re.search(
            rf"^{re.escape(spec['model'])}\s+([0-9a-f]+)\s+", list_text, re.MULTILINE
        )
        if match is None:
            identities.append({"model_key": model_key, "available": False, **spec})
            continue
        if match.group(1) != spec["model_id"]:
            raise RuntimeError(f"model ID mismatch: {model_key}")
        show = subprocess.run(
            ["wsl.exe", "-d", "Ubuntu", "--", "/usr/local/bin/ollama", "show", spec["model"]],
            check=True,
            capture_output=True,
        )
        (ROOT / f"metadata/{model_key}.show.stdout.bin").write_bytes(show.stdout)
        (ROOT / f"metadata/{model_key}.show.stderr.bin").write_bytes(show.stderr)
        show_text = show.stdout.decode("utf-8")
        if spec["quantization"] not in show_text:
            raise RuntimeError(f"quantization mismatch: {model_key}")
        blob_path = f"/home/msi/.ollama/models/blobs/sha256-{spec['payload_sha256']}"
        blob_hash = subprocess.run(
            ["wsl.exe", "-d", "Ubuntu", "--", "sha256sum", blob_path],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.split()[0]
        if blob_hash != spec["payload_sha256"]:
            raise RuntimeError(f"model payload mismatch: {model_key}")
        identity = {
            "model_key": model_key,
            "available": True,
            "provider": "local-wsl-ollama",
            "runtime": "Ollama",
            "runtime_version": "0.15.2",
            **spec,
        }
        config = {
            "provider": identity["provider"],
            "runtime": identity["runtime"],
            "runtime_version": identity["runtime_version"],
            "model": identity["model"],
            "model_id": identity["model_id"],
            "payload_sha256": identity["payload_sha256"],
            "format": identity["format"],
            "quantization": identity["quantization"],
            "ollama_flags": ["--format", "json", "--hidethinking", "--keepalive", "0"],
            "environment": {"OLLAMA_NOHISTORY": "1"},
            "retry_policy": "NO_RETRY_ONE_INVOCATION_PER_OBSERVATION",
        }
        identity["configuration_digest"] = digest_value(config)
        identities.append(identity)
        template_root = ROOT / "metadata/templates" / model_key
        template_root.mkdir(parents=True, exist_ok=True)
        for challenge_id in CHALLENGE_IDS:
            request = build_request(
                CHALLENGE_ROOT / f"{challenge_id}.json",
                evaluator_id=f"local-ollama-repeated-{model_key}",
                evaluator_version="ollama-0.15.2",
                config_digest=identity["configuration_digest"],
            )
            validate_frozen_v0_request_binding(request)
            assert_oracle_blind_request(request)
            request_without_lf = canonical_json_bytes(request)
            request_wire = request_without_lf + b"\n"
            prompt = prompt_bytes(request_without_lf)
            serialized = request_wire.decode("utf-8").lower()
            banned = [
                marker
                for marker in (
                    '"expected"',
                    '"expected_outcome"',
                    '"oracle"',
                    '"mismatch_classification"',
                    "unsafe_false_preservation",
                    "unsafe_unverifiable_upgrade",
                    "reference evaluator",
                )
                if marker in serialized
            ]
            secret_hits = [name for name, pattern in SECRET_PATTERNS.items() if pattern.search(prompt)]
            if banned or secret_hits:
                raise RuntimeError(f"evaluator-facing leakage: {model_key}/{challenge_id}: {banned}/{secret_hits}")
            (template_root / f"{challenge_id}.request.json").write_bytes(request_wire)
            (template_root / f"{challenge_id}.prompt.txt").write_bytes(prompt)
            leakage_checks.append(
                {
                    "model_key": model_key,
                    "challenge_id": challenge_id,
                    "request_guard": "PASS",
                    "answer_bearing_markers": banned,
                    "secret_markers": secret_hits,
                    "request_sha256": sha256_bytes(request_wire),
                    "prompt_sha256": sha256_bytes(prompt),
                }
            )

    if not any(identity["available"] for identity in identities):
        raise RuntimeError("no scheduled model is available")
    write_json(ROOT / "metadata/model-identities.json", {"schema": "prf-repeated-model-identities.v0", "models": identities})
    write_json(
        ROOT / "metadata/oracle-leakage-check.json",
        {
            "schema": "prf-repeated-oracle-leakage-check.v0",
            "status": "PASS",
            "templates_checked": len(leakage_checks),
            "answer_bearing_markers_found": 0,
            "secret_markers_found": 0,
            "checks": leakage_checks,
        },
    )
    write_json(
        ROOT / "metadata/methodology.json",
        {
            "schema": "prf-external-evaluator-repeated-methodology.v0",
            "starting_main": STARTING_MAIN,
            "frozen_v0_commit": V0_COMMIT,
            "frozen_v0_tree": V0_TREE,
            "adapter_commit": ADAPTER_COMMIT,
            "evaluator_output_schema_sha256": EVALUATOR_OUTPUT_SCHEMA_SHA256,
            "response_schema_sha256": RESPONSE_SCHEMA_SHA256,
            "model_order": list(MODEL_KEYS),
            "challenge_order": list(CHALLENGE_IDS),
            "runs_per_challenge": 10,
            "one_invocation_per_observation": True,
            "semantic_retries": 0,
            "no_conversation_memory": True,
            "capture_before_scoring": True,
            "initial_ollama_server_started_for_study": True,
            "instruction_sha256": hashlib.sha256(
                __import__("common").INSTRUCTION.encode("utf-8")
            ).hexdigest(),
        },
    )
    print(json.dumps({"status": "PREPARED", "models": identities, "templates": len(leakage_checks)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
