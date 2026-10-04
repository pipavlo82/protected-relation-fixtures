from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[1]
SUITE_PATH = ROOT / "conformance" / "award-actual-settlement-v0" / "suite.json"
PROFILE_ID = "award-actual-settlement-v0"
MAX_AMOUNT = 1000
BOUNDS = {"max_bidders": 2, "max_amount": MAX_AMOUNT, "units": 1, "accepted_completions": 1}
ASSUMPTIONS = ["same accepted successful performance at true cost", "loser incurs no work cost",
               "reveal bond refunded", "equal normalized transaction costs"]
EXPECTED_CASES = {
    "price_preserving": "PRESERVED",
    "fixed_reward_equal_price": "PRESERVED",
    "fixed_reward_substitution": "VIOLATED",
    "wrong_winner": "VIOLATED",
    "wrong_task": "VIOLATED",
    "wrong_tender": "VIOLATED",
    "unaccepted_work": "VIOLATED",
    "premature_award": "VIOLATED",
    "repeated_settlement": "VIOLATED",
    "missing_payment": "UNVERIFIABLE",
    "missing_award": "UNVERIFIABLE",
    "absent_settlement": "UNVERIFIABLE",
    "malformed_amount": "UNVERIFIABLE",
}


class ProfileError(ValueError):
    """A bounded profile or expectation cannot be established."""


def require(condition: bool, reason: str) -> None:
    if not condition:
        raise ProfileError(reason)


def _amount(value: Any) -> bool:
    return type(value) is int and 0 <= value <= MAX_AMOUNT


def _identifier(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def compute_award(
    bids: list[dict[str, Any]], reserve: int, units: int = 1,
) -> dict[str, Any] | None:
    """Single-unit procurement Vickrey rule, with input/commit-order ties."""
    require(type(units) is int and units == 1, "single_unit_required")
    require(_amount(reserve) and reserve > 0, "invalid_reserve")
    require(isinstance(bids, list) and len(bids) <= 2, "bounded_bid_list_required")
    bidders = set()
    for bid in bids:
        require(isinstance(bid, dict) and set(bid) == {"bidder", "amount"}, "invalid_bid")
        require(_identifier(bid["bidder"]) and _amount(bid["amount"]), "invalid_bid")
        require(bid["bidder"] not in bidders, "duplicate_bidder")
        bidders.add(bid["bidder"])
    ordered = sorted(bids, key=lambda bid: bid["amount"])
    if not ordered or ordered[0]["amount"] > reserve:
        return None
    price = min(ordered[1]["amount"], reserve) if len(ordered) == 2 else reserve
    return {"winner": ordered[0]["bidder"], "price": price}


def relation(award: Any, settlements: Any) -> dict[str, str]:
    """Compare an award obligation with observed accepted-work transfers.

    These are synthetic inputs, not authenticated chain evidence. A PRESERVED
    result establishes this bounded tuple only, never a global incentive claim.
    """
    def result(outcome: str, reason: str) -> dict[str, str]:
        return {"outcome": outcome, "reason": reason}

    award_fields = {"target_ref", "tender_id", "winner", "price", "finalized"}
    payment_fields = {"target_ref", "tender_id", "fulfiller", "amount", "accepted"}
    if not isinstance(award, dict) or set(award) != award_fields:
        return result("UNVERIFIABLE", "invalid_award")
    if (not all(_identifier(award[key]) for key in ("target_ref", "tender_id", "winner"))
            or not _amount(award["price"]) or type(award["finalized"]) is not bool):
        return result("UNVERIFIABLE", "invalid_award")
    if not isinstance(settlements, list) or not settlements:
        return result("UNVERIFIABLE", "missing_settlement")
    for payment in settlements:
        if not isinstance(payment, dict) or set(payment) != payment_fields:
            return result("UNVERIFIABLE", "invalid_settlement")
        if (not all(_identifier(payment[key]) for key in ("target_ref", "tender_id", "fulfiller"))
                or not _amount(payment["amount"]) or type(payment["accepted"]) is not bool):
            return result("UNVERIFIABLE", "invalid_settlement")
    if len(settlements) != 1:
        return result("VIOLATED", "completion_cardinality")
    payment = settlements[0]
    checks = (
        (award["finalized"], "award_not_finalized"),
        (payment["target_ref"] == award["target_ref"], "target_mismatch"),
        (payment["tender_id"] == award["tender_id"], "tender_mismatch"),
        (payment["fulfiller"] == award["winner"], "winner_mismatch"),
        (payment["accepted"], "work_not_accepted"),
        (payment["amount"] == award["price"], "amount_mismatch"),
    )
    for preserved, reason in checks:
        if not preserved:
            return result("VIOLATED", reason)
    return result("PRESERVED", "award_bound_to_actual_settlement")


def utility(cost: int, bidder: str, award: dict[str, Any] | None, actual_payment: int) -> int:
    """Normalized successful-work payoff; losers perform no work and receive 0."""
    require(_amount(cost) and _amount(actual_payment) and _identifier(bidder), "invalid_utility_input")
    require(award is None or (isinstance(award, dict) and _identifier(award.get("winner"))
                             and _amount(award.get("price"))), "invalid_utility_award")
    if award is None or award["winner"] != bidder:
        require(actual_payment == 0, "loser_payment_outside_profile")
        return 0
    return actual_payment - cost


def weak_projection(award: dict[str, Any], settlements: list[dict[str, Any]]) -> dict[str, Any]:
    """The core observation intentionally drops monetary settlement information."""
    return {"winner": award["winner"], "fulfillers": [p["fulfiller"] for p in settlements],
            "accepted": [p["accepted"] for p in settlements], "completions": len(settlements)}


def _unique_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value = {}
    for key, item in pairs:
        require(key not in value, f"duplicate_json_key:{key}")
        value[key] = item
    return value


def load_suite(path: Path = SUITE_PATH) -> dict[str, Any]:
    raw = path.read_bytes()
    require(bool(raw) and not raw.startswith(b"\xef\xbb\xbf") and b"\r" not in raw
            and raw.endswith(b"\n") and not raw.endswith(b"\n\n"), "invalid_suite_bytes")
    try:
        value = json.loads(raw.decode("utf-8"), object_pairs_hook=_unique_keys)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ProfileError("invalid_suite_json") from exc
    require(isinstance(value, dict), "suite_object_required")
    return value


def validate_suite(
    suite: dict[str, Any] | None = None,
    *, evaluator: Callable = relation, utility_evaluator: Callable = utility,
) -> dict[str, Any]:
    suite = load_suite() if suite is None else suite
    require(isinstance(suite, dict) and suite.get("profile_id") == PROFILE_ID, "unknown_profile")
    bounds = suite.get("bounds")
    require(suite.get("evidence_class") == "SYNTHETIC_CONDITIONAL_MODEL"
            and isinstance(bounds, dict) and bounds == BOUNDS
            and all(type(value) is int for value in bounds.values())
            and suite.get("assumptions") == ASSUMPTIONS,
            "profile_scope_or_assumptions_changed")
    cases = suite.get("cases")
    require(isinstance(cases, list) and all(isinstance(c, dict) for c in cases), "invalid_case_list")
    require(all(_identifier(c.get("id")) for c in cases), "invalid_case_identifier")
    require(len(cases) == len(EXPECTED_CASES)
            and {c.get("id") for c in cases} == set(EXPECTED_CASES), "required_cases_missing_or_duplicated")
    results = []
    by_id = {}
    for case in cases:
        case_id = case["id"]
        require(case.get("expected_outcome") == EXPECTED_CASES[case_id], f"expectation_changed:{case_id}")
        outcome = evaluator(case.get("award"), case.get("settlements"))
        require(isinstance(outcome, dict) and outcome.get("outcome") == EXPECTED_CASES[case_id],
                f"relation_mismatch:{case_id}")
        results.append({"id": case_id, **outcome})
        by_id[case_id] = case

    control = by_id["price_preserving"]
    fixed = by_id["fixed_reward_substitution"]
    equal_reward = by_id["fixed_reward_equal_price"]
    require(control.get("settlement_policy") == "award_price", "positive_payment_policy_changed")
    for case in (fixed, equal_reward):
        require(case.get("settlement_policy") == "fixed_reward"
                and _amount(case.get("fixed_reward"))
                and case["fixed_reward"] == case["settlements"][0]["amount"],
                "fixed_reward_payment_context_changed")
    require(equal_reward["fixed_reward"] == equal_reward["award"]["price"], "equality_control_changed")
    require(weak_projection(control["award"], control["settlements"])
            == weak_projection(fixed["award"], fixed["settlements"]), "weak_projection_not_preserved")
    require(control["award"] == fixed["award"], "core_award_changed")
    require(len(fixed["settlements"]) == 1, "core_completion_count_changed")
    fixed_payment_without_substitution = dict(fixed["settlements"][0])
    fixed_payment_without_substitution["amount"] = control["settlements"][0]["amount"]
    require(fixed_payment_without_substitution == control["settlements"][0], "core_payment_axis_not_isolated")
    require(control["award"]["price"] == 50 and fixed["settlements"][0]["amount"] == 100,
            "core_payment_witness_changed")

    # Derive both allocations independently of fixture outcome labels.
    experiment = suite.get("incentive_experiment")
    expected_experiment = {"cost": 60, "reserve": 100, "fixed_reward": 100,
                           "truthful_bid": 60, "deviation_bid": 49, "other_bid": 50}
    require(experiment == expected_experiment, "incentive_witness_changed")
    payoffs = {}
    for mode in ("price_preserving", "eligibility_only_fixed_reward"):
        values = []
        for bid in (experiment["truthful_bid"], experiment["deviation_bid"]):
            award = compute_award([{"bidder": "A", "amount": bid},
                                   {"bidder": "B", "amount": experiment["other_bid"]}], experiment["reserve"])
            actual_payment = 0
            if award is not None and award["winner"] == "A":
                actual_payment = award["price"] if mode == "price_preserving" else experiment["fixed_reward"]
            payoff = utility_evaluator(experiment["cost"], "A", award, actual_payment)
            require(type(payoff) is int, "invalid_utility_result")
            values.append(payoff)
        payoffs[mode] = {"truthful": values[0], "deviation": values[1], "gain": values[1] - values[0]}
    require(payoffs["price_preserving"] == {"truthful": 0, "deviation": -10, "gain": -10},
            "price_preserving_payoff_mismatch")
    require(payoffs["eligibility_only_fixed_reward"] == {"truthful": 0, "deviation": 40, "gain": 40},
            "actual_payment_guarantee_transfer")
    return {"profile_id": PROFILE_ID, "cases": results, "weak_projection_preserved": True,
            "payoffs": payoffs, "scope": "synthetic_single_unit_successful_work"}
