# Award-to-actual-settlement v0

This additive, synthetic study tests whether actual accepted-work settlement preserves a finalized procurement award. It sits outside the frozen `corpus/v0` contract. The protected relation includes the payment amount; allocation eligibility alone cannot establish it.

## Bounded contract

The model covers one procurement unit, at most two bidders, and integer bids, costs, prices and rewards in `0..1000`. The reserve is a positive integer in `1..1000`. Lowest eligible bid wins; ties use stable commitment order. Price-preserving settlement pays the lower of reserve and the other bidder's bid, or reserve when no competitor exists.

For a finalized award and a list of observed completion transfers, preservation requires:

- identical opaque synthetic `target_ref` and `tender_id`;
- transfer `fulfiller` equal to award `winner`;
- `accepted` exactly `true`;
- exactly one observed completion;
- actual transfer `amount` equal to `award.price`.

Complete matching evidence yields `PRESERVED`; a concrete mismatch yields `VIOLATED`, including an explicit `finalized: false`. Missing or malformed evidence yields `UNVERIFIABLE`, including an empty transfer list: `[]` means unavailable completion evidence, not proof of zero economic settlement. These outcomes follow the repository's [outcome model](../../spec/outcome-model.md). Opaque references bind only the supplied records; they do not validate task versions, award-time authority, signatures, chain state, or provenance. Repeated transfer records violate the bounded observed cardinality; this does not prove chain replay prevention. Multi-unit procurement is outside this profile.

The weak projection observes the winning fulfiller, accepted work and one completion while dropping price. A transfer of 100 can therefore preserve that projection while violating an award of 50. Eligibility-only fixed reward is a legitimate different payment policy; when reward differs from auction price, it cannot inherit a theorem whose utility uses that price.

## Source boundary and counterexample

The [sealed-bid companion discussion](https://ethereum-magicians.org/t/sealed-bid-award-mechanism-for-task-tenders-companion-to-erc-8183-8195-8414/29814/4) motivates this study. Reviewed upstream is `shentonyan/sealed-bid-award-erc` at `725a0f77adc13f602bfe9b3e9eb43756a8a280d9`:

- [Lean utility L34–48](https://github.com/shentonyan/sealed-bid-award-erc/blob/725a0f77adc13f602bfe9b3e9eb43756a8a280d9/proofs/VickreyTruthful.lean#L34-L48) pays `award.price - cost`; [the theorem L117–131](https://github.com/shentonyan/sealed-bid-award-erc/blob/725a0f77adc13f602bfe9b3e9eb43756a8a280d9/proofs/VickreyTruthful.lean#L117-L131) uses that utility.
- [Adapter test L74](https://github.com/shentonyan/sealed-bid-award-erc/blob/725a0f77adc13f602bfe9b3e9eb43756a8a280d9/test/adapter8414.test.js#L74) checks price 60; [L91–93](https://github.com/shentonyan/sealed-bid-award-erc/blob/725a0f77adc13f602bfe9b3e9eb43756a8a280d9/test/adapter8414.test.js#L91-L93) intentionally pays fixed reward 100.
- [Draft L175–179](https://github.com/shentonyan/sealed-bid-award-erc/blob/725a0f77adc13f602bfe9b3e9eb43756a8a280d9/erc/erc-draft_sealed_bid_award.md#L175-L179) describes eligibility-only composition and claims incentive compatibility when `reserve = reward`.

Let reserve and fixed reward both be 100, A's cost be 60, and B's bid be 50:

| A's bid | A's result | A's fixed-reward utility | A's price-preserving utility |
| --- | --- | --- | --- |
| 60 (truthful) | loses | 0 | 0 |
| 49 (deviation) | wins; auction price 50 | 100 - 60 = 40 | 50 - 60 = -10 |

The witness assumes the same acceptable performance, refunded reveal bond, no losing work cost, and equal normalized transaction costs. With unequal costs, the deviation's extra costs must be less than 40; bounded costs alone are insufficient. This does not refute the Lean theorem or establish a deployed exploit or ERC conformance failure. The upstream [MockTaskToken L4–8](https://github.com/shentonyan/sealed-bid-award-erc/blob/725a0f77adc13f602bfe9b3e9eb43756a8a280d9/test/mocks/MockTaskToken.sol#L4-L8) is explicitly test-only and nonconforming.

## Executable checks

```text
python tools/validate_award_actual_settlement.py
python -m unittest discover -s tests -p test_award_actual_settlement.py -v
python -O -m unittest discover -s tests -p test_award_actual_settlement.py -v
```

The CLI emits JSON for 13 relation cases: 2 `PRESERVED`, 7 `VIOLATED` and 4 `UNVERIFIABLE`, plus recomputed payoffs.

Controls include matching price-preserving settlement and fixed reward equal to price. Adversarial cases vary amount, winner, task reference, tender, acceptance, finalization and completion cardinality; malformed or unavailable evidence remains fail-closed. Mutation controls remove those checks or collapse `UNVERIFIABLE` into `PRESERVED`. Economic controls reject substituting award price for actual fixed reward and reject `reserve = reward` as a sufficient truthfulness condition.

A bounded positive grid uses costs and declared bids `{0,49,50,60,100,101}`, the same competitor bids or no competitor, reserves `{1,50,100}`, and both commitment orders: 1,512 comparisons. It checks price-preserving truthful utility against deviations within this grid, not a universal mechanism proof.
