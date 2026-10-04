# Award-to-actual-settlement v0

This additive, synthetic study tests whether actual accepted-work settlement preserves a finalized procurement award. It sits outside the frozen `corpus/v0` contract. The protected relation includes the payment amount; allocation eligibility alone cannot establish it.

## Standards and integration scope

The mechanism source is an **unnumbered sealed-bid award companion draft**. Its references to ERC-8183, ERC-8195 and ERC-8414 provide composition context. The behavior exercised by this profile is explicit below:

| Reference | Role in this profile | Coverage limit |
| --- | --- | --- |
| Unnumbered sealed-bid companion | Bounded lowest-bid procurement, award price and actual accepted-work settlement; comparison of price-preserving and eligibility-only fixed-reward policies. | Synthetic integer model with one unit and at most two bidders. |
| ERC-8414 | The pinned `adapter8414.test.js` supplies the source example where auction price 60 and fixed reward 100 differ. | Its `MockTaskToken` is test-only and nonconforming. Full ERC-8414 interfaces and behavior are outside this model. |
| ERC-8183 and ERC-8195 | Context named by the companion discussion and draft. | No behavior specific to either ERC is implemented or assessed here. |

Within **Protected Relation Fixtures (PRF)**, this profile protects the supplied finalized-award-to-completion relation, including the actual payment amount, and uses the repository's three outcomes described below. It does not establish full conformance to any of the named ERCs.

A **Semantic ABI** description and **recompute-kit** adapter are possible follow-up integrations after PRF verification. Neither integration is included in this profile; these checks establish no guarantee about their cores or adapters.

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

Run from the repository root. The first three commands exercise this profile; the final two run the full repository test suite:

```text
python tools/validate_award_actual_settlement.py
python -m unittest discover -s tests -p test_award_actual_settlement.py -v
python -O -m unittest discover -s tests -p test_award_actual_settlement.py -v
python -m unittest discover -s tests -v
python -O -m unittest discover -s tests -v
```

The CLI emits JSON for 13 relation cases: 2 `PRESERVED`, 7 `VIOLATED` and 4 `UNVERIFIABLE`, plus recomputed payoffs.

Controls include matching price-preserving settlement and fixed reward equal to price. Adversarial cases vary amount, winner, task reference, tender, acceptance, finalization and completion cardinality; malformed or unavailable evidence remains fail-closed. Mutation controls remove those checks or collapse `UNVERIFIABLE` into `PRESERVED`. Economic controls reject substituting award price for actual fixed reward and reject `reserve = reward` as a sufficient truthfulness condition.

A bounded positive grid uses costs and declared bids `{0,49,50,60,100,101}`, the same competitor bids or no competitor, reserves `{1,50,100}`, and both commitment orders: 1,512 comparisons. It checks price-preserving truthful utility against deviations within this grid, not a universal mechanism proof.

These Python checks execute synthetic fixtures and recompute their outcomes and payoffs. They do not execute the upstream Lean proof, Solidity adapter harness or a deployed chain integration. The [source manifest](sources.json) records the upstream pin, source-file hashes and inspection date, and marks those upstream executions as `NOT_RUN`. The base discussion page was inspected; its direct post URL was unavailable during source verification.

## Windows checkout and repository verification

The root `.gitattributes` is itself a frozen v0 artifact and remains byte-for-byte unchanged. Its listed ordinary technical text formats use LF. The hash-bound Codex payload has an additive, narrowly scoped `-text -eol` rule in its [lane `.gitattributes`](../../evidence/external-evaluators/v0/codex-gpt56-sol-repeated/.gitattributes): Git must preserve the committed payload bytes even with Windows `core.autocrlf=true`. This includes LF captures, intentional CRLF captures and binary data. The existing attributes for the other captured evidence lanes remain in effect. No corpus payload is renormalized and no global Git configuration is required.

Attributes apply when Git materializes files. A fresh checkout uses these rules automatically; an existing checkout may still contain files converted by the older rules. Preserve local edits before restoring only affected tracked captures from the index. The checkout regression uses Git's actual conversion filters with `core.autocrlf=true` and `core.eol=crlf`; final verification also compares a fresh ordinary Windows worktree with the committed blobs. Frozen contract artifacts and captured datasets must retain their exact bytes. Unclassified ordinary text follows the pre-existing Git policy; in particular, Windows may materialize `LICENSE` as CRLF without changing its committed blob.

In addition to the profile and full-suite commands above, run the checkout regression and repository validators:

```text
python -m unittest discover -s tests -p test_gitattributes.py -v
python -O -m unittest discover -s tests -p test_gitattributes.py -v
python tools/validate_manifest.py
python tools/validate_seed_corpus.py
python tools/validate_relation_discrimination.py
python tools/validate_v0_freeze.py
python tools/validate_external_evaluator_evidence.py
python tools/validate_external_evaluator_repeated_evidence.py
python tools/validate_codex_gpt56_repeated_evidence.py
python tools/validate_trustless_ai_deterministic_case_study.py
python tools/validate_invinoveritas_epistemic_basis_v18.py
```

The acceptance checks cover normal and optimized Python execution, the profile's positive and adversarial controls, captured-byte checkout behavior, and the unchanged frozen-v0 tree and digests. Test results belong to the tested revision and environment; they establish neither upstream proof execution nor full ERC or deployed-system conformance.
