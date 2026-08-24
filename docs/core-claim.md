# Core Claim

## Normative rule

Equality under a weak observation must not imply equivalence of the protected semantic relation.

## Operational rule

Do not trust a preserved projection; recompute the protected semantic object and compare that instead.

## Why this exists

Many verifiers and benchmark families are strong at detecting raw differences but weak at detecting false equivalence under coarse projections. These fixtures target the opposite failure mode:

- a weak observable still passes
- the protected semantic relation has changed
- a fail-closed verifier must refuse to mint a false PASS

## Minimal benchmark question

For each fixture:

1. Was the weak projection preserved?
2. Was the protected semantic relation preserved?
3. If the answer is yes to (1) and no to (2), did the verifier fail closed?
