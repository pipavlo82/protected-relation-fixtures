from __future__ import annotations

import copy
import json
from pathlib import Path
import tempfile
import unittest

from tools.award_actual_settlement import (
    ProfileError,
    compute_award,
    load_suite,
    relation,
    utility,
    validate_suite,
)


VALUES = (0, 49, 50, 60, 100, 101)


def reference_award(own_bid: int, rival_bid: int | None, reserve: int, own_first: bool):
    """Independent two-bidder oracle, expressed as an eligibility threshold."""
    if own_bid > reserve:
        return {"winner": "B", "price": reserve} if rival_bid is not None and rival_bid <= reserve else None
    if rival_bid is None or rival_bid > reserve:
        return {"winner": "A", "price": reserve}
    own_wins = own_bid < rival_bid or (own_bid == rival_bid and own_first)
    return {
        "winner": "A" if own_wins else "B",
        "price": rival_bid if own_wins else own_bid,
    }


class AwardActualSettlementTests(unittest.TestCase):
    def setUp(self) -> None:
        self.award = {
            "target_ref": "task:example:v1",
            "tender_id": "tender-1",
            "winner": "A",
            "price": 50,
            "finalized": True,
        }
        self.settlement = {
            "target_ref": "task:example:v1",
            "tender_id": "tender-1",
            "fulfiller": "A",
            "amount": 50,
            "accepted": True,
        }

    def _bids(self, own_bid: int, rival_bid: int | None, own_first: bool):
        bids = [{"bidder": "A", "amount": own_bid}]
        if rival_bid is not None:
            rival = {"bidder": "B", "amount": rival_bid}
            bids = bids + [rival] if own_first else [rival] + bids
        return bids

    def _own_payment(self, award, amount: int) -> int:
        return amount if award is not None and award["winner"] == "A" else 0

    def _mutant(self, reason: str):
        def evaluate(award, settlements):
            result = relation(award, settlements)
            if result["reason"] != reason:
                return result
            changed_award = copy.deepcopy(award)
            changed_settlements = copy.deepcopy(settlements)
            if reason == "completion_cardinality":
                changed_settlements = changed_settlements[:1]
            elif reason == "award_not_finalized":
                changed_award["finalized"] = True
            elif reason == "target_mismatch":
                changed_settlements[0]["target_ref"] = changed_award["target_ref"]
            elif reason == "tender_mismatch":
                changed_settlements[0]["tender_id"] = changed_award["tender_id"]
            elif reason == "winner_mismatch":
                changed_settlements[0]["fulfiller"] = changed_award["winner"]
            elif reason == "work_not_accepted":
                changed_settlements[0]["accepted"] = True
            elif reason == "amount_mismatch":
                changed_settlements[0]["amount"] = changed_award["price"]
            else:
                self.fail(f"unknown mutation: {reason}")
            return relation(changed_award, changed_settlements)

        return evaluate

    def test_fixed_reward_counterexample_and_price_preserving_control(self) -> None:
        truthful = compute_award(self._bids(60, 50, True), 100)
        deviating = compute_award(self._bids(49, 50, True), 100)
        self.assertEqual(truthful, {"winner": "B", "price": 60})
        self.assertEqual(deviating, {"winner": "A", "price": 50})
        self.assertEqual(utility(60, "A", truthful, 0), 0)
        self.assertEqual(utility(60, "A", deviating, 100), 40)
        self.assertEqual(utility(60, "A", deviating, 50), -10)
        preserved = relation(self.award, [self.settlement])
        fixed_reward = copy.deepcopy(self.settlement)
        fixed_reward["amount"] = 100
        violated = relation(self.award, [fixed_reward])
        self.assertEqual(preserved["outcome"], "PRESERVED")
        self.assertEqual(violated["outcome"], "VIOLATED")
        self.assertEqual(violated["reason"], "amount_mismatch")

    def test_price_preserving_payment_is_dominant_on_independent_bounded_grid(self) -> None:
        comparisons = 0
        fixed_reward_improvements = 0
        for reserve in (1, 50, 100):
            for cost in VALUES:
                for deviation in VALUES:
                    for rival in (None, *VALUES):
                        for own_first in (True, False):
                            with self.subTest(reserve=reserve, cost=cost, deviation=deviation, rival=rival, own_first=own_first):
                                truthful = compute_award(self._bids(cost, rival, own_first), reserve)
                                deviating = compute_award(self._bids(deviation, rival, own_first), reserve)
                                self.assertEqual(truthful, reference_award(cost, rival, reserve, own_first))
                                self.assertEqual(deviating, reference_award(deviation, rival, reserve, own_first))
                                truth_payment = self._own_payment(truthful, truthful["price"] if truthful is not None else 0)
                                deviation_payment = self._own_payment(deviating, deviating["price"] if deviating is not None else 0)
                                truth_utility = utility(cost, "A", truthful, truth_payment)
                                deviation_utility = utility(cost, "A", deviating, deviation_payment)
                                self.assertEqual(truth_utility, truth_payment - cost if truthful is not None and truthful["winner"] == "A" else 0)
                                self.assertEqual(deviation_utility, deviation_payment - cost if deviating is not None and deviating["winner"] == "A" else 0)
                                self.assertGreaterEqual(truth_utility, deviation_utility)
                                if utility(cost, "A", deviating, self._own_payment(deviating, 100)) > utility(cost, "A", truthful, self._own_payment(truthful, 100)):
                                    fixed_reward_improvements += 1
                                comparisons += 1
        self.assertEqual(comparisons, 1512)
        self.assertGreater(fixed_reward_improvements, 0)

    def test_no_bid_and_reserve_boundary_controls(self) -> None:
        self.assertIsNone(compute_award([], 100))
        self.assertEqual(compute_award([{"bidder": "A", "amount": 60}], 100), {"winner": "A", "price": 100})
        self.assertEqual(compute_award([{"bidder": "A", "amount": 100}], 100), {"winner": "A", "price": 100})
        self.assertIsNone(compute_award([{"bidder": "A", "amount": 101}], 100))
        self.assertEqual(compute_award(self._bids(49, 101, True), 100), {"winner": "A", "price": 100})
        self.assertIsNone(compute_award(self._bids(101, 101, True), 100))

    def test_equal_bids_use_declared_input_order(self) -> None:
        self.assertEqual(compute_award(self._bids(50, 50, True), 100), {"winner": "A", "price": 50})
        self.assertEqual(compute_award(self._bids(50, 50, False), 100), {"winner": "B", "price": 50})

    def test_unsupported_auction_shapes_are_rejected(self) -> None:
        invalid = [
            (None, 100, 1),
            ({"bidder": "A", "amount": 50}, 100, 1),
            ([{"bidder": "A"}], 100, 1),
            ([{"bidder": "A", "amount": 50, "extra": 1}], 100, 1),
            ([{"bidder": "", "amount": 50}], 100, 1),
            ([{"bidder": "A", "amount": True}], 100, 1),
            ([{"bidder": "A", "amount": -1}], 100, 1),
            ([{"bidder": "A", "amount": 1001}], 100, 1),
            ([{"bidder": "A", "amount": 50.0}], 100, 1),
            ([{"bidder": "A", "amount": 50}, {"bidder": "A", "amount": 49}], 100, 1),
            ([{"bidder": name, "amount": 50} for name in ("A", "B", "C")], 100, 1),
            ([], 0, 1),
            ([], -1, 1),
            ([], 1001, 1),
            ([], True, 1),
            ([], 100.0, 1),
            ([], 100, 2),
            ([], 100, True),
        ]
        for bids, reserve, units in invalid:
            with self.subTest(bids=bids, reserve=reserve, units=units):
                with self.assertRaises(ProfileError):
                    compute_award(bids, reserve, units)

    def test_actual_payment_drives_winner_utility(self) -> None:
        self.assertEqual(utility(60, "A", {"winner": "A", "price": 50}, 100), 40)
        self.assertEqual(utility(60, "A", {"winner": "A", "price": 50}, 0), -60)
        self.assertEqual(utility(60, "A", {"winner": "B", "price": 100}, 0), 0)
        self.assertEqual(utility(60, "A", None, 0), 0)

    def test_equal_fixed_reward_preserves_only_observed_payment_relation(self) -> None:
        award = copy.deepcopy(self.award)
        award["price"] = 100
        payment = copy.deepcopy(self.settlement)
        payment["amount"] = 100
        self.assertEqual(relation(award, [payment])["outcome"], "PRESERVED")

    def test_matching_reserve_and_fixed_reward_is_insufficient_for_truthful_dominance(self) -> None:
        suite = load_suite()
        experiment = suite["incentive_experiment"]
        self.assertEqual(experiment["fixed_reward"], experiment["reserve"])
        fixed_payoffs = validate_suite(suite)["payoffs"]["eligibility_only_fixed_reward"]
        self.assertEqual(fixed_payoffs["truthful"], 0)
        self.assertEqual(fixed_payoffs["deviation"], 40)
        self.assertGreater(fixed_payoffs["gain"], 0)

    def test_payments_to_losers_and_malformed_utility_inputs_are_outside_profile(self) -> None:
        for award in (None, {"winner": "B", "price": 100}):
            with self.subTest(award=award):
                with self.assertRaises(ProfileError):
                    utility(60, "A", award, 100)
        for cost, bidder, payment in ((True, "A", 100), (-1, "A", 100), (1001, "A", 100), (60, "", 100), (60, "A", True), (60, "A", -1), (60, "A", 1001)):
            with self.subTest(cost=cost, bidder=bidder, payment=payment):
                with self.assertRaises(ProfileError):
                    utility(cost, bidder, {"winner": "A", "price": 50}, payment)
        for award in ({}, {"winner": "A"}, {"winner": "A", "price": True}, []):
            with self.subTest(malformed_award=award):
                with self.assertRaises(ProfileError):
                    utility(60, "A", award, 100)

    def test_missing_award_or_settlement_evidence_fails_closed(self) -> None:
        for award in (None, [], {}, "award"):
            with self.subTest(award=award):
                self.assertEqual(relation(award, [self.settlement])["outcome"], "UNVERIFIABLE")
        for settlements in (None, [], {}, "settlement", [None], [{}]):
            with self.subTest(settlements=settlements):
                self.assertEqual(relation(self.award, settlements)["outcome"], "UNVERIFIABLE")
        for field in self.award:
            incomplete = copy.deepcopy(self.award)
            del incomplete[field]
            with self.subTest(missing_award_field=field):
                self.assertEqual(relation(incomplete, [self.settlement])["outcome"], "UNVERIFIABLE")
        for field in self.settlement:
            incomplete = copy.deepcopy(self.settlement)
            del incomplete[field]
            with self.subTest(missing_settlement_field=field):
                self.assertEqual(relation(self.award, [incomplete])["outcome"], "UNVERIFIABLE")

    def test_malformed_or_extended_evidence_fails_closed(self) -> None:
        award_mutations = (
            ("target_ref", None), ("tender_id", ""), ("winner", 1),
            ("price", True), ("price", -1), ("price", 1001), ("price", 50.0),
            ("finalized", 1), ("extra", "unsupported"),
        )
        settlement_mutations = (
            ("target_ref", None), ("tender_id", ""), ("fulfiller", 1),
            ("amount", None), ("amount", True), ("amount", -1),
            ("amount", 1001), ("amount", 50.0), ("accepted", "yes"),
            ("extra", "unsupported"),
        )
        for field, value in award_mutations:
            malformed = copy.deepcopy(self.award)
            malformed[field] = value
            with self.subTest(award_field=field, value=value):
                self.assertEqual(relation(malformed, [self.settlement])["outcome"], "UNVERIFIABLE")
        for field, value in settlement_mutations:
            malformed = copy.deepcopy(self.settlement)
            malformed[field] = value
            with self.subTest(settlement_field=field, value=value):
                self.assertEqual(relation(self.award, [malformed])["outcome"], "UNVERIFIABLE")

    def test_concrete_binding_and_completion_violations(self) -> None:
        changes = (
            ("target_ref", "task:example:v2", "target_mismatch"),
            ("tender_id", "tender-2", "tender_mismatch"),
            ("fulfiller", "B", "winner_mismatch"),
            ("amount", 100, "amount_mismatch"),
            ("accepted", False, "work_not_accepted"),
        )
        for field, value, reason in changes:
            changed = copy.deepcopy(self.settlement)
            changed[field] = value
            with self.subTest(field=field):
                result = relation(self.award, [changed])
                self.assertEqual(result["outcome"], "VIOLATED")
                self.assertEqual(result["reason"], reason)
        unfinalized = copy.deepcopy(self.award)
        unfinalized["finalized"] = False
        self.assertEqual(relation(unfinalized, [self.settlement]), {"outcome": "VIOLATED", "reason": "award_not_finalized"})
        replayed = relation(self.award, [self.settlement, copy.deepcopy(self.settlement)])
        self.assertEqual(replayed, {"outcome": "VIOLATED", "reason": "completion_cardinality"})

    def test_canonical_suite_is_deterministic_and_matches_every_declared_case(self) -> None:
        suite = load_suite()
        report = validate_suite(suite)
        self.assertEqual(report["profile_id"], "award-actual-settlement-v0")
        self.assertEqual(len(report["cases"]), 13)
        self.assertEqual([case["outcome"] for case in report["cases"]].count("PRESERVED"), 2)
        self.assertEqual([case["outcome"] for case in report["cases"]].count("VIOLATED"), 7)
        self.assertEqual([case["outcome"] for case in report["cases"]].count("UNVERIFIABLE"), 4)
        self.assertTrue(report["weak_projection_preserved"])
        self.assertEqual(report["payoffs"], {
            "price_preserving": {"truthful": 0, "deviation": -10, "gain": -10},
            "eligibility_only_fixed_reward": {"truthful": 0, "deviation": 40, "gain": 40},
        })
        self.assertEqual(report, validate_suite(copy.deepcopy(suite)))
        for case in suite["cases"]:
            with self.subTest(case=case["id"]):
                self.assertEqual(relation(case["award"], case["settlements"])["outcome"], case["expected_outcome"])

    def test_each_relation_check_mutation_is_killed_and_keeps_positive_controls(self) -> None:
        suite = load_suite()
        for reason in (
            "target_mismatch", "tender_mismatch", "winner_mismatch",
            "work_not_accepted", "amount_mismatch", "award_not_finalized",
            "completion_cardinality",
        ):
            mutant = self._mutant(reason)
            with self.subTest(omitted_check=reason):
                for case in suite["cases"]:
                    if case["expected_outcome"] == "PRESERVED":
                        self.assertEqual(mutant(case["award"], case["settlements"])["outcome"], "PRESERVED")
                self.assertEqual(mutant(self.award, [self.settlement])["outcome"], "PRESERVED")
                self.assertEqual(mutant(self.award, [])["outcome"], "UNVERIFIABLE")
                incomplete = copy.deepcopy(self.settlement)
                del incomplete["amount"]
                self.assertEqual(mutant(self.award, [incomplete])["outcome"], "UNVERIFIABLE")
                with self.assertRaises(ProfileError):
                    validate_suite(suite, evaluator=mutant)

    def test_unverifiable_upgrade_mutation_is_killed_and_keeps_positive_controls(self) -> None:
        def optimistic_evaluator(award, settlements):
            result = relation(award, settlements)
            if result["outcome"] == "UNVERIFIABLE":
                return {"outcome": "PRESERVED", "reason": "optimistic_missing_evidence"}
            return result

        suite = load_suite()
        for case in suite["cases"]:
            if case["expected_outcome"] == "PRESERVED":
                self.assertEqual(optimistic_evaluator(case["award"], case["settlements"])["outcome"], "PRESERVED")
        self.assertEqual(optimistic_evaluator(self.award, [])["outcome"], "PRESERVED")
        with self.assertRaises(ProfileError):
            validate_suite(suite, evaluator=optimistic_evaluator)

    def test_price_based_utility_mutation_cannot_inherit_fixed_reward_guarantee(self) -> None:
        def price_based_utility(cost, bidder, award, actual_payment):
            payment = award["price"] if award is not None and award["winner"] == bidder else 0
            return utility(cost, bidder, award, payment)

        truthful = compute_award(self._bids(60, 50, True), 100)
        deviating = compute_award(self._bids(49, 50, True), 100)
        self.assertEqual(price_based_utility(60, "A", truthful, 0), 0)
        self.assertEqual(price_based_utility(60, "A", deviating, 50), -10)
        self.assertNotEqual(price_based_utility(60, "A", deviating, 100), 40)
        with self.assertRaises(ProfileError):
            validate_suite(utility_evaluator=price_based_utility)

    def test_missing_mandatory_case_is_rejected(self) -> None:
        suite = load_suite()
        for index, case in enumerate(suite["cases"]):
            changed = copy.deepcopy(suite)
            del changed["cases"][index]
            with self.subTest(removed=case["id"]):
                with self.assertRaises(ProfileError):
                    validate_suite(changed)

    def test_mutated_oracle_expectations_are_rejected(self) -> None:
        suite = load_suite()
        for index, case in enumerate(suite["cases"]):
            changed = copy.deepcopy(suite)
            changed["cases"][index]["expected_outcome"] = "VIOLATED" if case["expected_outcome"] == "PRESERVED" else "PRESERVED"
            with self.subTest(case=case["id"]):
                with self.assertRaises(ProfileError):
                    validate_suite(changed)

    def test_missing_or_duplicated_case_identity_is_rejected(self) -> None:
        suite = load_suite()
        changed = copy.deepcopy(suite)
        del changed["cases"][0]["id"]
        with self.assertRaises(ProfileError):
            validate_suite(changed)
        changed = copy.deepcopy(suite)
        changed["cases"].append(copy.deepcopy(changed["cases"][0]))
        with self.assertRaises(ProfileError):
            validate_suite(changed)
        changed = copy.deepcopy(suite)
        changed["cases"][0]["id"] = []
        with self.assertRaises(ProfileError):
            validate_suite(changed)

    def test_profile_context_and_payment_policy_mutations_are_rejected(self) -> None:
        suite = load_suite()
        for field in ("bounds", "assumptions", "evidence_class"):
            changed = copy.deepcopy(suite)
            del changed[field]
            with self.subTest(missing_context=field):
                with self.assertRaises(ProfileError):
                    validate_suite(changed)
        for bound, value in (
            ("max_bidders", 3), ("max_amount", 1001), ("units", 2),
            ("accepted_completions", 2), ("units", True),
            ("accepted_completions", True), ("max_bidders", 2.0),
        ):
            changed = copy.deepcopy(suite)
            changed["bounds"][bound] = value
            with self.subTest(bound=bound, value=value):
                with self.assertRaises(ProfileError):
                    validate_suite(changed)
        changed = copy.deepcopy(suite)
        changed["assumptions"].remove("reveal bond refunded")
        with self.assertRaises(ProfileError):
            validate_suite(changed)
        changed = copy.deepcopy(suite)
        changed["evidence_class"] = "AUTHENTICATED_CHAIN_EVIDENCE"
        with self.assertRaises(ProfileError):
            validate_suite(changed)
        for case_id, field, value in (
            ("price_preserving", "settlement_policy", "fixed_reward"),
            ("fixed_reward_substitution", "settlement_policy", "award_price"),
            ("fixed_reward_equal_price", "settlement_policy", "award_price"),
            ("fixed_reward_substitution", "fixed_reward", 50),
            ("fixed_reward_equal_price", "fixed_reward", 51),
            ("fixed_reward_equal_price", "fixed_reward", False),
        ):
            changed = copy.deepcopy(suite)
            case = next(case for case in changed["cases"] if case["id"] == case_id)
            case[field] = value
            with self.subTest(case=case_id, field=field, value=value):
                with self.assertRaises(ProfileError):
                    validate_suite(changed)
        for field, value in (
            ("target_ref", "task:other:v2"), ("tender_id", "other-tender"),
            ("fulfiller", "B"), ("accepted", False),
        ):
            changed = copy.deepcopy(suite)
            case = next(case for case in changed["cases"] if case["id"] == "fixed_reward_substitution")
            case["settlements"][0][field] = value
            with self.subTest(core_payment_field=field):
                with self.assertRaises(ProfileError):
                    validate_suite(changed)
        for field in suite["incentive_experiment"]:
            changed = copy.deepcopy(suite)
            changed["incentive_experiment"][field] += 1
            with self.subTest(experiment_field=field):
                with self.assertRaises(ProfileError):
                    validate_suite(changed)

    def test_suite_bytes_and_json_duplicate_keys_are_checked(self) -> None:
        canonical = (json.dumps(load_suite(), ensure_ascii=False, indent=2) + "\n").encode("utf-8")
        malformed = (
            canonical[:-1], b"\xef\xbb\xbf" + canonical,
            canonical.replace(b"\n", b"\r\n"), canonical + b"\n",
            b"\xff\n", b"{invalid}\n", b"[]\n",
            b'{"profile_id":"first","profile_id":"second"}\n',
        )
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "suite.json"
            path.write_bytes(canonical)
            self.assertEqual(load_suite(path), load_suite())
            for value in malformed:
                with self.subTest(bytes=value[:40]):
                    path.write_bytes(value)
                    with self.assertRaises(ProfileError):
                        load_suite(path)


if __name__ == "__main__":
    unittest.main()
