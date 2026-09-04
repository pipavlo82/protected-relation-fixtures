from __future__ import annotations

import json
from pathlib import Path

from common import (
    CHALLENGE_IDS,
    MODEL_KEYS,
    ROOT,
    RUN_INDICES,
    load_json,
    observation_root,
    sha256_bytes,
    write_json,
)


def main() -> int:
    observations = []
    per_model = {}
    per_challenge = {}
    for model_key in MODEL_KEYS:
        block = load_json(ROOT / f"metadata/model-blocks/{model_key}.json")
        if block.get("capture_complete") is not True:
            raise RuntimeError(f"incomplete model block: {model_key}")
        per_model[model_key] = block
        if block.get("available") is not True:
            continue
        for challenge_id in CHALLENGE_IDS:
            challenge_rows = []
            for run_index in RUN_INDICES:
                path = observation_root(model_key, challenge_id, run_index) / "observation.json"
                row = load_json(path)
                if row["model_key"] != model_key or row["challenge_id"] != challenge_id or row["run_index"] != run_index:
                    raise RuntimeError(f"observation identity mismatch: {path}")
                observations.append(row)
                challenge_rows.append(row)
            per_challenge.setdefault(challenge_id, {})[model_key] = {
                "scheduled": 10,
                "attempted": len(challenge_rows),
                "captured": len(challenge_rows),
                "valid_semantic_responses": sum(row["adapter_status"] == "RESPONSE_VALID" for row in challenge_rows),
                "adapter_failures": sum(row["adapter_status"] != "RESPONSE_VALID" for row in challenge_rows),
            }

    inventory_entries = []
    inventory_roots = [ROOT / model_key for model_key in MODEL_KEYS if (ROOT / model_key).exists()]
    inventory_roots.extend([ROOT / "metadata", ROOT / "harness"])
    files = []
    for base in inventory_roots:
        files.extend(path for path in base.rglob("*") if path.is_file())
    for path in sorted(set(files), key=lambda item: item.relative_to(ROOT).as_posix()):
        raw = path.read_bytes()
        inventory_entries.append(
            {
                "path": path.relative_to(ROOT).as_posix(),
                "byte_length": len(raw),
                "sha256": sha256_bytes(raw),
            }
        )
    inventory = {
        "schema": "prf-repeated-capture-inventory.v0",
        "entries": inventory_entries,
        "total_files": len(inventory_entries),
        "total_bytes": sum(row["byte_length"] for row in inventory_entries),
    }
    write_json(ROOT / "capture-inventory.json", inventory)
    inventory_digest = sha256_bytes((ROOT / "capture-inventory.json").read_bytes())
    valid = sum(row["adapter_status"] == "RESPONSE_VALID" for row in observations)
    summary = {
        "schema": "prf-external-evaluator-repeated-capture-summary.v0",
        "capture_closed": True,
        "scoring_performed": False,
        "scheduled_observations": sum(row["scheduled"] for row in per_model.values()),
        "attempted_observations": len(observations),
        "captured_observations": len(observations),
        "valid_semantic_responses": valid,
        "adapter_failures": len(observations) - valid,
        "per_model": per_model,
        "per_challenge": per_challenge,
        "capture_inventory": {
            "path": "capture-inventory.json",
            "sha256": inventory_digest,
            "total_files": inventory["total_files"],
            "total_bytes": inventory["total_bytes"],
        },
    }
    write_json(ROOT / "capture-summary.json", summary)
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
