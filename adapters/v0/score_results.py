from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
from typing import Any

if __package__:
    from .contract import (
        ADAPTER_STATUSES,
        AdapterContractViolation,
        digest_value,
        require,
        validate_frozen_v0_request_binding,
        validate_response,
    )
else:
    from contract import (
        ADAPTER_STATUSES,
        AdapterContractViolation,
        digest_value,
        require,
        validate_frozen_v0_request_binding,
        validate_response,
    )


ROOT = Path(__file__).resolve().parents[2]
ORACLE_PATH = ROOT / "corpus" / "v0" / "oracle" / "expected-results.json"
MANIFEST_PATH = ROOT / "corpus" / "v0" / "manifest.json"
ORACLE_SHA256 = "8fa93a5ef4a61c3a7d80c8951c131e694d4947f16a9f38c9c813dd0a29a0b6e5"
MANIFEST_SHA256 = "ab83841f2703848bbb6be592f075c8e62098dcd768bee530eebe5c8ec48a3ee8"
CLASSIFICATION_NAMES = (
    "MATCH",
    "UNSAFE_FALSE_PRESERVATION",
    "UNSAFE_UNVERIFIABLE_UPGRADE",
    "FALSE_VIOLATION",
    "PRESERVATION_NOT_ESTABLISHED",
    "VIOLATION_NOT_ESTABLISHED",
    "UNVERIFIABLE_MISCLASSIFIED_AS_VIOLATION",
)


def classify(expected: str, actual: str) -> str:
    if expected == actual:
        return "MATCH"
    table = {
        ("VIOLATED", "PRESERVED"): "UNSAFE_FALSE_PRESERVATION",
        ("UNVERIFIABLE", "PRESERVED"): "UNSAFE_UNVERIFIABLE_UPGRADE",
        ("PRESERVED", "VIOLATED"): "FALSE_VIOLATION",
        ("PRESERVED", "UNVERIFIABLE"): "PRESERVATION_NOT_ESTABLISHED",
        ("VIOLATED", "UNVERIFIABLE"): "VIOLATION_NOT_ESTABLISHED",
        ("UNVERIFIABLE", "VIOLATED"): "UNVERIFIABLE_MISCLASSIFIED_AS_VIOLATION",
    }
    try:
        return table[(expected, actual)]
    except KeyError as exc:
        raise AdapterContractViolation(f"unclassifiable semantic outcomes: {expected}/{actual}") from exc


def _load_exact_authority(path: Path, expected_digest: str, label: str) -> dict[str, Any]:
    raw = path.read_bytes()
    require(hashlib.sha256(raw).hexdigest() == expected_digest, f"{label.upper()}_IDENTITY_MISMATCH")
    try:
        value = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise AdapterContractViolation(f"invalid {label}: {exc}") from exc
    require(isinstance(value, dict), f"{label} must be an object")
    return value


def score_results(
    requests: list[dict[str, Any]],
    transcripts: list[dict[str, Any]],
    *,
    oracle_path: Path = ORACLE_PATH,
    manifest_path: Path = MANIFEST_PATH,
) -> dict[str, Any]:
    oracle = _load_exact_authority(oracle_path, ORACLE_SHA256, "oracle")
    _load_exact_authority(manifest_path, MANIFEST_SHA256, "manifest")
    request_map: dict[str, dict[str, Any]] = {}
    for request in requests:
        validate_frozen_v0_request_binding(request)
        challenge_id = request["challenge_id"]
        require(challenge_id not in request_map, f"duplicate request: {challenge_id}")
        request_map[challenge_id] = request
    require(len(transcripts) == len(request_map), "request/transcript count mismatch")

    classifications: Counter[str] = Counter()
    adapter_failures: Counter[str] = Counter()
    details: list[dict[str, Any]] = []
    seen: set[str] = set()
    for transcript in transcripts:
        require(isinstance(transcript, dict), "transcript must be an object")
        status = transcript.get("adapter_status")
        require(status in ADAPTER_STATUSES, f"unknown adapter status: {status}")
        evaluator = transcript.get("evaluator")
        candidates = [request for request in request_map.values() if request["evaluator"] == evaluator]
        require(bool(candidates), "transcript evaluator does not match any request")
        matching = [request for request in candidates if digest_value(request) == transcript.get("request_digest")]
        require(len(matching) == 1, "transcript request digest mismatch")
        request = matching[0]
        challenge_id = request["challenge_id"]
        require(challenge_id not in seen, f"duplicate transcript: {challenge_id}")
        seen.add(challenge_id)
        if status != "RESPONSE_VALID":
            adapter_failures[status] += 1
            details.append({"challenge_id": challenge_id, "adapter_status": status, "classification": None})
            continue
        response = validate_response(request, transcript.get("normalized_response"))
        require(transcript.get("response_digest") == digest_value(response), "transcript response digest mismatch")
        expected = oracle["results"][challenge_id]["semantic_outcome"]
        classification = classify(expected, response["outcome"])
        classifications[classification] += 1
        details.append(
            {
                "challenge_id": challenge_id,
                "adapter_status": status,
                "semantic_outcome": response["outcome"],
                "classification": classification,
            }
        )
    require(seen == set(request_map), "missing transcript")
    evaluated = sum(classifications.values())
    counts = {name: classifications[name] for name in CLASSIFICATION_NAMES}
    rates = {name: (counts[name] / evaluated if evaluated else 0.0) for name in CLASSIFICATION_NAMES}
    return {
        "schema": "protected-relation-external-adapter-score.v0",
        "requests": len(requests),
        "semantic_responses": evaluated,
        "adapter_failures": dict(sorted(adapter_failures.items())),
        "adapter_failure_total": sum(adapter_failures.values()),
        "classifications": counts,
        "classification_rates": rates,
        "details": sorted(details, key=lambda row: row["challenge_id"]),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("requests", type=Path)
    parser.add_argument("transcripts", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    try:
        requests = json.loads(args.requests.read_text(encoding="utf-8"))
        transcripts = json.loads(args.transcripts.read_text(encoding="utf-8"))
        report = score_results(requests, transcripts)
    except (OSError, json.JSONDecodeError, AdapterContractViolation, KeyError) as exc:
        print(f"adapter scoring: FAIL: {exc}")
        return 1
    rendered = json.dumps(report, indent=2, ensure_ascii=False) + "\n"
    if args.output:
        args.output.write_text(rendered, encoding="utf-8", newline="\n")
    else:
        print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
