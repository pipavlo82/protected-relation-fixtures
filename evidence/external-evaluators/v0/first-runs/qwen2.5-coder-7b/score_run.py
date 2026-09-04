from __future__ import annotations

import json
from pathlib import Path
import sys


REPO = Path(
    r"C:\Users\msi\Documents\Codex\2026-08-25\we-are-closing-the-erc-8309"
    r"\protected-relation-fixtures"
)
ROOT = Path(r"D:\prf-experiments\qwen2.5-coder-7b-first-run")
THREE_B = Path(r"D:\prf-experiments\qwen2.5-3b-instruct-post-wrapper-repair\final-results.json")
sys.path.insert(0, str(REPO))

from adapters.v0.score_results import ORACLE_PATH, score_results  # noqa: E402


EXPECTED_IDS = [f"prf-{index:03d}" for index in range(1, 7)]


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")


def comparison_kind(three_b: dict[str, object], seven_b: dict[str, object]) -> str:
    three_valid = three_b["adapter_status"] == "RESPONSE_VALID"
    seven_valid = seven_b["adapter_status"] == "RESPONSE_VALID"
    if three_valid and seven_valid:
        return "SAME_SEMANTIC_JUDGMENT" if three_b["model_outcome"] == seven_b["model_outcome"] else "SEMANTIC_DISAGREEMENT"
    if three_valid:
        return "THREE_B_SEMANTIC_JUDGMENT_VS_SEVEN_B_ADAPTER_FAILURE"
    if seven_valid:
        return "THREE_B_ADAPTER_FAILURE_VS_SEVEN_B_SEMANTIC_JUDGMENT"
    return "BOTH_ADAPTER_FAILURE"


def main() -> int:
    capture = json.loads((ROOT / "capture-summary.json").read_text(encoding="utf-8"))
    if capture.get("capture_complete") is not True or capture.get("model_calls") != 6:
        raise RuntimeError("all six raw model calls must be frozen before scoring")
    requests = [json.loads((ROOT / f"requests/{challenge_id}.json").read_text(encoding="utf-8")) for challenge_id in EXPECTED_IDS]
    transcripts = [
        json.loads((ROOT / f"transcripts/{challenge_id}.transcript.json").read_text(encoding="utf-8"))
        for challenge_id in EXPECTED_IDS
    ]
    report = score_results(requests, transcripts)
    oracle = json.loads(ORACLE_PATH.read_text(encoding="utf-8"))
    detail_by_id = {row["challenge_id"]: row for row in report["details"]}
    rows = []
    for request, transcript in zip(requests, transcripts, strict=True):
        challenge_id = request["challenge_id"]
        detail = detail_by_id[challenge_id]
        rows.append(
            {
                "challenge_id": challenge_id,
                "protected_relation": request["protected_relation_profile"]["kind"],
                "request_sha256": transcript["request_digest"],
                "raw_output_sha256": transcript["raw_response_digest"],
                "wrapped_response_sha256": transcript["response_digest"],
                "invocation_context_sha256": transcript["invocation_digest"],
                "adapter_status": transcript["adapter_status"],
                "model_outcome": (
                    transcript["evaluator_output"]["outcome"]
                    if transcript["evaluator_output"] is not None
                    else None
                ),
                "expected_v0_outcome": oracle["results"][challenge_id]["semantic_outcome"],
                "classification": detail["classification"],
            }
        )

    three_b = json.loads(THREE_B.read_text(encoding="utf-8"))
    three_by_id = {row["challenge_id"]: row for row in three_b["rows"]}
    seven_by_id = {row["challenge_id"]: row for row in rows}
    comparison = []
    for challenge_id in EXPECTED_IDS:
        old = three_by_id[challenge_id]
        new = seven_by_id[challenge_id]
        comparison.append(
            {
                "challenge_id": challenge_id,
                "qwen2.5_3b": old["model_outcome"],
                "qwen2.5_3b_status": old["adapter_status"],
                "qwen2.5_coder_7b": new["model_outcome"],
                "qwen2.5_coder_7b_status": new["adapter_status"],
                "expected_v0_outcome": new["expected_v0_outcome"],
                "difference": comparison_kind(old, new),
            }
        )

    result = {
        "schema": "prf-qwen25-coder-7b-first-run-result.v0",
        "interpretation": "ONE FIRST-RUN SAMPLE PER CHALLENGE",
        "rows": rows,
        "aggregates": report,
        "comparison_with_qwen2.5_3b_post_wrapper_repair": comparison,
    }
    write_json(ROOT / "score-report.json", report)
    write_json(ROOT / "comparison-with-qwen2.5-3b.json", comparison)
    write_json(ROOT / "final-results.json", result)
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
