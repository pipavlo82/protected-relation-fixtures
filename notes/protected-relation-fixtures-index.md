# Protected Relation Fixtures вЂ” Index

**Status:** benchmark seed index
**Purpose:** tie together the emerging protected-relation fixture lane without mixing it into frozen TSEI authority-run artifacts.

## Core framing

This lane explores cases where:

- a weak observation or projection is preserved;
- the protected semantic relation is not preserved;
- a verifier must fail closed rather than mint a false PASS.

Core normative rule:

> Equality under a weak observation must not imply equivalence of the protected semantic relation.

Operational rule:

> Do not trust a preserved projection; recompute the protected semantic object and compare that instead.

## Seed notes

- `research-local-neighborhood-vs-global-identity.md`
- `protected-relation-fixtures-one-page.md`

## Current seed fixture cards

1. `fixture-01-local-neighborhood-identity.md`
   - same degree / local count
   - different protected neighborhood identity

2. `fixture-02-relation-type-loss.md`
   - same topology / adjacency shape
   - different relation meaning

3. `fixture-03-version-skew-unverifiable.md`
   - downstream parsing still works
   - protected state must remain `UNVERIFIABLE`

4. `fixture-04-multiplicity-collapse.md`
   - same neighbor set
   - different multiplicity / repeated semantic links

5. `fixture-05-pass-pass-compose-fail.md`
   - each step looks locally admissible
   - composition breaks the protected relation

## Suggested next fixtures

- optional local-scope-vs-global-scope drift fixture
- optional unknown-as-empty fixture split out from version-skew

## Minimal benchmark shape

For each fixture, ask:

1. Was the weak projection preserved?
2. Was the protected semantic relation preserved?
3. If (1 = yes) and (2 = no), did the verifier fail closed?

## Why this lane matters

This is a strong complement to TSEI because it isolates false-equivalence cases
that arise when observers preserve only counts, local structure, vocabulary,
or transport-level compatibility while semantic identity has already drifted.

