from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys


REPO = Path(
    r"C:\Users\msi\Documents\Codex\2026-08-25\we-are-closing-the-erc-8309"
    r"\protected-relation-fixtures"
)
ROOT = Path(r"D:\prf-experiments\qwen2.5-3b-instruct-first-run")
sys.path.insert(0, str(REPO))

from adapters.v0.score_results import ORACLE_PATH, score_results  # noqa: E402


def load_json(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: object) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def main() -> int:
    capture = load_json(ROOT / "capture-summary.json")
    if not capture.get("capture_complete") or capture.get("model_calls") != 6:
        raise RuntimeError("all six raw captures must be frozen before scoring")
    ids = [f"prf-{index:03d}" for index in range(1, 7)]
    requests = [load_json(ROOT / "requests" / f"{challenge_id}.request.json") for challenge_id in ids]
    transcripts = [load_json(ROOT / "transcripts" / f"{challenge_id}.transcript.json") for challenge_id in ids]
    for challenge_id, transcript in zip(ids, transcripts, strict=True):
        raw = (ROOT / "raw" / f"{challenge_id}.stdout.bin").read_bytes()
        if hashlib.sha256(raw).hexdigest() != transcript["raw_response_digest"]:
            raise RuntimeError(f"raw response drift before scoring: {challenge_id}")

    report = score_results(requests, transcripts)
    write_json(ROOT / "score-report.json", report)

    oracle = load_json(ORACLE_PATH)
    detail_by_id = {row["challenge_id"]: row for row in report["details"]}
    rows = []
    for request, transcript in zip(requests, transcripts, strict=True):
        challenge_id = request["challenge_id"]
        normalized = transcript["normalized_response"]
        rows.append(
            {
                "challenge_id": challenge_id,
                "protected_relation": request["protected_relation_profile"]["kind"],
                "request_sha256": hashlib.sha256(
                    (ROOT / "requests" / f"{challenge_id}.request.json").read_bytes()
                ).hexdigest(),
                "prompt_sha256": hashlib.sha256(
                    (ROOT / "prompts" / f"{challenge_id}.prompt.txt").read_bytes()
                ).hexdigest(),
                "raw_response_sha256": transcript["raw_response_digest"],
                "normalized_response_sha256": transcript["response_digest"],
                "adapter_status": transcript["adapter_status"],
                "model_outcome": normalized.get("outcome") if normalized else None,
                "expected_v0_outcome": oracle["results"][challenge_id]["semantic_outcome"],
                "classification": detail_by_id[challenge_id]["classification"],
            }
        )
    final = {
        "schema": "prf-qwen25-3b-first-run-result.v0",
        "interpretation": "ONE FIRST-RUN SAMPLE PER CHALLENGE",
        "rows": rows,
        "aggregates": report,
    }
    write_json(ROOT / "final-results.json", final)
    print(json.dumps(final, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
