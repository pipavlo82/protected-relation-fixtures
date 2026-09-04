from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


CHALLENGES = tuple(f"prf-{index:03d}" for index in range(1, 7))
RUNS = tuple(range(1, 11))


def sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")


def main() -> int:
    root = Path(r"D:\prf-experiments\codex-gpt56-sol-repeated-v0")
    phase = json.loads((root / "metadata/capture-phase-complete.json").read_text(encoding="utf-8"))
    if phase != {
        **phase,
        "capture_complete": True,
        "scoring_started": False,
        "scheduled_observations": 60,
        "attempted_observations": 60,
        "captured_observations": 60,
    }:
        raise RuntimeError("capture phase is not closed before scoring")
    observations = []
    seen = set()
    for challenge in CHALLENGES:
        for run_index in RUNS:
            path = root / "isolated" / challenge / f"run-{run_index:02d}" / "observation.json"
            row = json.loads(path.read_text(encoding="utf-8"))
            identity = (row.get("challenge_id"), row.get("run_index"))
            if identity != (challenge, run_index) or identity in seen:
                raise RuntimeError(f"observation identity mismatch: {path}")
            seen.add(identity)
            observations.append(row)
    excluded = {"capture-inventory.json", "capture-summary.json"}
    files = [
        path
        for path in root.rglob("*")
        if path.is_file() and path.relative_to(root).as_posix() not in excluded
    ]
    entries = []
    for path in sorted(files, key=lambda item: item.relative_to(root).as_posix()):
        raw = path.read_bytes()
        entries.append(
            {
                "path": path.relative_to(root).as_posix(),
                "byte_length": len(raw),
                "sha256": sha256(raw),
            }
        )
    inventory = {
        "schema": "prf-codex-gpt56-capture-inventory.v0",
        "capture_closed": True,
        "entries": entries,
        "total_files": len(entries),
        "total_bytes": sum(entry["byte_length"] for entry in entries),
    }
    write_json(root / "capture-inventory.json", inventory)
    valid = sum(row["adapter_status"] == "RESPONSE_VALID" for row in observations)
    per_challenge = {}
    for challenge in CHALLENGES:
        block = [row for row in observations if row["challenge_id"] == challenge]
        per_challenge[challenge] = {
            "scheduled": 10,
            "attempted": len(block),
            "captured": len(block),
            "valid_semantic_responses": sum(row["adapter_status"] == "RESPONSE_VALID" for row in block),
            "adapter_failures": sum(row["adapter_status"] != "RESPONSE_VALID" for row in block),
        }
    summary = {
        "schema": "prf-codex-gpt56-capture-summary.v0",
        "capture_closed": True,
        "scoring_performed": False,
        "scheduled_observations": 60,
        "attempted_observations": len(observations),
        "captured_observations": len(observations),
        "valid_semantic_responses": valid,
        "adapter_failures": len(observations) - valid,
        "per_challenge": per_challenge,
        "capture_inventory": {
            "path": "capture-inventory.json",
            "sha256": sha256((root / "capture-inventory.json").read_bytes()),
            "total_files": inventory["total_files"],
            "total_bytes": inventory["total_bytes"],
        },
        "capture_closed_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "timestamp_authoritative": False,
    }
    write_json(root / "capture-summary.json", summary)
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
