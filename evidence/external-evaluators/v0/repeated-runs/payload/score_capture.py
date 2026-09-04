from __future__ import annotations

from collections import Counter
from itertools import combinations
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parent
REPO = Path(r"C:\Users\msi\Documents\Codex\2026-08-25\we-are-closing-the-erc-8309\protected-relation-fixtures")
sys.path.insert(0, str(REPO))

from adapters.v0.score_results import CLASSIFICATION_NAMES, score_results  # noqa: E402


MODELS = (
    "qwen2.5-3b-instruct",
    "qwen2.5-coder-7b",
    "llama3.1-8b",
)
CHALLENGES = tuple(f"prf-{index:03d}" for index in range(1, 7))
OUTCOMES = ("PRESERVED", "VIOLATED", "UNVERIFIABLE")
UNSAFE = ("UNSAFE_FALSE_PRESERVATION", "UNSAFE_UNVERIFIABLE_UPGRADE")
FIRST_RUN_IDS = {
    "qwen2.5-3b-instruct": "qwen2.5-3b-post-wrapper-repair",
    "qwen2.5-coder-7b": "qwen2.5-coder-7b",
    "llama3.1-8b": "llama3.1-8b",
}


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def write(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")


def rate(numerator: int, denominator: int):
    return {
        "numerator": numerator,
        "denominator": denominator,
        "decimal": round(numerator / denominator, 12) if denominator else None,
    }


def expected_map():
    oracle = load(REPO / "corpus/v0/oracle/expected-results.json")
    return {key: row["semantic_outcome"] for key, row in oracle["results"].items()}


def first_run_map():
    matrix = load(REPO / "evidence/external-evaluators/v0/first-run-matrix.json")
    if "qwen2.5-3b-pre-wrapper-repair" in matrix["comparable_experiments"]:
        raise RuntimeError("pre-wrapper evidence is not a comparable semantic baseline")
    by_experiment = {row["experiment_id"]: row for row in matrix["models"]}
    result = {}
    for model, experiment in FIRST_RUN_IDS.items():
        rows = {row["challenge_id"]: row for row in by_experiment[experiment]["observations"]}
        result[model] = rows
    return result


def main() -> int:
    capture = load(ROOT / "capture-summary.json")
    if not capture.get("capture_closed") or capture.get("scoring_performed"):
        raise RuntimeError("capture closure missing or already marked as scored")
    if capture["captured_observations"] != 180:
        raise RuntimeError("capture is incomplete")

    expected = expected_map()
    historical = first_run_map()
    observation_rows = []
    matrix_models = []
    stability_models = []
    scoring_dir = ROOT / "scoring"

    for model in MODELS:
        model_observations = []
        model_challenges = []
        model_stability = []
        aggregate_classifications = Counter()
        aggregate_statuses = Counter()
        for challenge in CHALLENGES:
            rows = []
            outcomes = Counter()
            classifications = Counter()
            statuses = Counter()
            for run_index in range(1, 11):
                base = ROOT / model / challenge / f"run-{run_index:02d}"
                observation = load(base / "observation.json")
                request = load(base / "request.json")
                transcript = load(base / "transcript.json")
                score = score_results([request], [transcript])
                detail = score["details"][0]
                status = detail["adapter_status"]
                outcome = detail.get("semantic_outcome")
                classification = detail.get("classification")
                statuses[status] += 1
                aggregate_statuses[status] += 1
                if outcome is not None:
                    outcomes[outcome] += 1
                if classification is not None:
                    classifications[classification] += 1
                    aggregate_classifications[classification] += 1
                row = {
                    "model_key": model,
                    "challenge_id": challenge,
                    "protected_relation": request["protected_relation_profile"]["kind"],
                    "run_index": run_index,
                    "scheduled_observations": 1,
                    "adapter_status": status,
                    "semantic_outcome": outcome,
                    "frozen_expected_outcome": expected[challenge],
                    "benchmark_classification": classification,
                    "request_bytes_sha256": observation["request_bytes_sha256"],
                    "stdout_sha256": observation["stdout_sha256"],
                    "stderr_sha256": observation["stderr_sha256"],
                    "evaluator_output_digest": observation["evaluator_output_digest"],
                    "wrapped_response_digest": observation["wrapped_response_digest"],
                    "invocation_context_digest": observation["invocation_context_digest"],
                }
                write(scoring_dir / model / challenge / f"run-{run_index:02d}.json", row)
                rows.append(row)
                observation_rows.append(row)

            valid = sum(outcomes.values())
            adapter_failures = 10 - valid
            modal_count = max(outcomes.values()) if valid else 0
            modal_outcomes = sorted(key for key, value in outcomes.items() if value == modal_count) if valid else []
            pair_total = valid * (valid - 1) // 2
            same_pairs = sum(value * (value - 1) // 2 for value in outcomes.values())
            disagree_pairs = pair_total - same_pairs
            previous = historical[model][challenge]
            previous_outcome = previous["evaluator_outcome"]
            if previous["adapter_status"] != "RESPONSE_VALID":
                recurrence = "HISTORICAL_ADAPTER_FAILURE"
            elif outcomes[previous_outcome] == 0:
                recurrence = "DID_NOT_RECUR"
            elif previous_outcome in modal_outcomes:
                recurrence = "RECURRED_MODAL"
            else:
                recurrence = "RECURRED_NONMODAL"
            unsafe_count = sum(classifications[name] for name in UNSAFE)
            challenge_record = {
                "challenge_id": challenge,
                "protected_relation": rows[0]["protected_relation"],
                "frozen_expected_outcome": expected[challenge],
                "scheduled_observations": 10,
                "valid_semantic_observations": valid,
                "adapter_failures": adapter_failures,
                "adapter_status_counts": dict(sorted(statuses.items())),
                "outcome_counts": {name: outcomes[name] for name in OUTCOMES},
                "classification_counts": {name: classifications[name] for name in CLASSIFICATION_NAMES},
                "classification_rates_scheduled": {
                    name: rate(classifications[name], 10) for name in CLASSIFICATION_NAMES
                },
                "classification_rates_valid": {
                    name: rate(classifications[name], valid) for name in CLASSIFICATION_NAMES
                },
                "unsafe_observed_rate": rate(unsafe_count, 10),
                "conditional_valid_unsafe_rate": rate(unsafe_count, valid),
                "modal_outcomes": modal_outcomes,
                "modal_outcome_share": rate(modal_count, valid) if valid else "NOT_COMPUTABLE",
                "nonmodal_valid_judgment_rate": rate(valid - modal_count, valid) if valid else "NOT_COMPUTABLE",
                "pairwise_semantic_disagreement_rate": (
                    rate(disagree_pairs, pair_total) if pair_total else "NOT_COMPUTABLE"
                ),
                "historical_first_run": {
                    "experiment_id": FIRST_RUN_IDS[model],
                    "adapter_status": previous["adapter_status"],
                    "semantic_outcome": previous_outcome,
                    "benchmark_classification": previous["mismatch_classification"],
                    "fresh_distribution_recurrence": recurrence,
                    "counted_in_fresh_denominator": False,
                },
                "observations": rows,
            }
            model_challenges.append(challenge_record)
            model_stability.append({key: challenge_record[key] for key in (
                "challenge_id", "protected_relation", "valid_semantic_observations", "adapter_failures",
                "outcome_counts", "modal_outcomes", "modal_outcome_share", "nonmodal_valid_judgment_rate",
                "pairwise_semantic_disagreement_rate", "historical_first_run"
            )})
            model_observations.extend(rows)

        valid_model = sum(row["adapter_status"] == "RESPONSE_VALID" for row in model_observations)
        model_summary = {
            "model_key": model,
            "scheduled_observations": 60,
            "attempted_observations": 60,
            "captured_observations": 60,
            "valid_semantic_observations": valid_model,
            "adapter_failures": 60 - valid_model,
            "adapter_status_counts": dict(sorted(aggregate_statuses.items())),
            "classification_counts": {name: aggregate_classifications[name] for name in CLASSIFICATION_NAMES},
            "challenges": model_challenges,
        }
        matrix_models.append(model_summary)
        stability_models.append({"model_key": model, "challenges": model_stability})

    total_classifications = Counter(
        row["benchmark_classification"] for row in observation_rows if row["benchmark_classification"] is not None
    )
    total_statuses = Counter(row["adapter_status"] for row in observation_rows)
    repeated_matrix = {
        "schema": "prf-external-evaluator-repeated-run-matrix.v0",
        "fresh_observation_policy": {
            "scheduled": 180,
            "one_call_per_observation": True,
            "semantic_retries": 0,
            "historical_first_runs_counted_in_denominator": False,
            "pre_wrapper_repair_used_as_comparable_baseline": False,
        },
        "overall": {
            "scheduled_observations": 180,
            "attempted_observations": 180,
            "captured_observations": 180,
            "valid_semantic_observations": sum(total_classifications.values()),
            "adapter_failures": 180 - sum(total_classifications.values()),
            "adapter_status_counts": dict(sorted(total_statuses.items())),
            "classification_counts": {name: total_classifications[name] for name in CLASSIFICATION_NAMES},
            "security_significant_failures": sum(total_classifications[name] for name in UNSAFE),
        },
        "models": matrix_models,
    }

    stability = {
        "schema": "prf-external-evaluator-semantic-stability-summary.v0",
        "denominator_rule": "valid semantic judgments only; adapter failures excluded",
        "frequency_interpretation": "empirical observed frequencies, not calibrated probabilities",
        "models": stability_models,
    }

    cross_challenges = []
    repeated_unsafe = []
    for challenge in CHALLENGES:
        records = {model["model_key"]: next(row for row in model["challenges"] if row["challenge_id"] == challenge)
                   for model in matrix_models}
        unsafe_false_models = [model for model, row in records.items()
                               if row["classification_counts"]["UNSAFE_FALSE_PRESERVATION"] > 0]
        unsafe_upgrade_models = [model for model, row in records.items()
                                 if row["classification_counts"]["UNSAFE_UNVERIFIABLE_UPGRADE"] > 0]
        for name, models in (("UNSAFE_FALSE_PRESERVATION", unsafe_false_models),
                             ("UNSAFE_UNVERIFIABLE_UPGRADE", unsafe_upgrade_models)):
            if len(models) >= 2:
                repeated_unsafe.append({
                    "challenge_id": challenge,
                    "protected_relation": next(iter(records.values()))["protected_relation"],
                    "classification": name,
                    "models": models,
                    "counts_by_model": {model: records[model]["classification_counts"][name] for model in models},
                })
        outcome_sets = {model: {name for name, count in row["outcome_counts"].items() if count}
                        for model, row in records.items()}
        union = set().union(*outcome_sets.values())
        all_determinately_same = len(union) == 1 and all(len(values) == 1 for values in outcome_sets.values())
        all_match = all(row["adapter_failures"] == 0 and row["classification_counts"]["MATCH"] == 10
                        for row in records.values())
        all_mismatch = all(row["valid_semantic_observations"] > 0 and row["classification_counts"]["MATCH"] == 0
                           for row in records.values())
        cross_challenges.append({
            "challenge_id": challenge,
            "protected_relation": next(iter(records.values()))["protected_relation"],
            "outcomes_observed_by_model": {model: sorted(values) for model, values in outcome_sets.items()},
            "models_disagree_semantically": len(union) > 1,
            "all_evaluated_models_agree_on_one_outcome": all_determinately_same,
            "all_evaluated_models_match_all_valid_observations": all_match,
            "all_evaluated_models_have_no_match": all_mismatch,
            "unsafe_false_preservation_models": unsafe_false_models,
            "unsafe_unverifiable_upgrade_models": unsafe_upgrade_models,
        })

    cross = {
        "schema": "prf-external-evaluator-cross-model-repeated-summary.v0",
        "minimum_models_for_repeated_cross_model_finding": 2,
        "repeated_security_significant_findings": repeated_unsafe,
        "challenges": cross_challenges,
        "claim_boundary": (
            "These are benchmark-relative findings from exact recorded invocations; they are not universal, "
            "deterministic, statistically significant by themselves, or external-domain truth."
        ),
    }

    write(ROOT / "repeated-run-matrix.json", repeated_matrix)
    write(ROOT / "stability-summary.json", stability)
    write(ROOT / "cross-model-summary.json", cross)
    scoring_summary = {
        "schema": "prf-external-evaluator-repeated-scoring-summary.v0",
        "capture_summary_sha256": __import__("hashlib").sha256((ROOT / "capture-summary.json").read_bytes()).hexdigest(),
        "observations_scored": len(observation_rows),
        "valid_semantic_observations": repeated_matrix["overall"]["valid_semantic_observations"],
        "adapter_failures": repeated_matrix["overall"]["adapter_failures"],
        "classification_counts": repeated_matrix["overall"]["classification_counts"],
        "outputs": {
            name: __import__("hashlib").sha256((ROOT / name).read_bytes()).hexdigest()
            for name in ("repeated-run-matrix.json", "stability-summary.json", "cross-model-summary.json")
        },
    }
    write(ROOT / "scoring-summary.json", scoring_summary)
    print(json.dumps(scoring_summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
