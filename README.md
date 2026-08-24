# Protected Relation Fixtures

Protected Relation Fixtures is a benchmark corpus for cases where weak observational equality is preserved while the protected semantic relation is not. It is designed for fail-closed verifiers, provenance systems, and transformation-stability methods that must distinguish count/shape preservation from actual semantic preservation.

## Core normative claim

> Equality under a weak observation must not imply equivalence of the protected semantic relation.

Operational version:

> Do not trust a preserved projection; recompute the protected semantic object and compare that instead.

## What this repo is

This repo is a small but serious benchmark seed for false-equivalence cases:

- local structure looks unchanged while protected identity has drifted;
- topology is preserved while relation meaning has changed;
- downstream parsing still works while semantic status must remain fail-closed;
- multiplicity-sensitive meaning is collapsed into set-like observations;
- individually acceptable transformations compose into semantic failure.

## What this repo is not

This repo is not:

- a frozen TSEI authority-run artifact set;
- a ReceiptOS run-history repository;
- a claim that every fixture here already has a machine-readable canonical vector format;
- a substitute for independently recomputing the protected semantic object.

## Current canonical fixture set

1. **Local neighborhood preserved, global identity changed**
2. **Relation type changed, shape preserved**
3. **Version skew / unknown-member collapse**
4. **Multiplicity collapse**
5. **Pass, pass, compose, fail**

## Minimal benchmark question

For each fixture:

1. Was the weak projection preserved?
2. Was the protected semantic relation preserved?
3. If the answer is yes to (1) and no to (2), did the verifier fail closed?

## Repository layout

```text
protected-relation-fixtures/
  README.md
  ROADMAP.md
  docs/
    core-claim.md
    fixture-design-principles.md
  fixtures/
    fixture-01-local-neighborhood-identity.md
    fixture-02-relation-type-loss.md
    fixture-03-version-skew-unverifiable.md
    fixture-04-multiplicity-collapse.md
    fixture-05-pass-pass-compose-fail.md
  notes/
    protected-relation-fixtures-one-page.md
    protected-relation-fixtures-index.md
```

## Design principles

- Make the protected relation explicit.
- Separate weak observation from protected semantics.
- Prefer fail-closed expectations over optimistic interpretation.
- Include real-world as well as synthetic cases.
- Do not treat one preserved view as proof of semantic preservation.

## Status

Current state: **benchmark seed / methodology nucleus**.

This repo already has a coherent starter corpus and framing, but it is still early-stage. The next expected steps are better canonical fixture formatting, clearer benchmark metadata, and eventual vectors/tests/adapters.

## Relation to TSEI, ReceiptOS, and Chronicle-style systems

- **TSEI**: this repo is a pressure-test lane for cases where preserved projections can tempt a verifier into overclaiming preserved semantics.
- **ReceiptOS**: this repo can serve as an adversarial fixture corpus for independently recomputable receipt/verifier paths that must fail closed on false equivalence.
- **Chronicle-style systems**: this repo is relevant wherever ordered event continuity or observable stability can be misread as preserved semantic identity.

In short: this repo is not a replacement for those systems. It is a benchmark layer for testing whether they distinguish weak observational preservation from actual protected semantic preservation.

## Why keep this separate

This repo is intentionally separate from any single TSEI run lane or overloaded product repository. The point is to give protected-relation fixtures their own identity so they can be reused across TSEI, Trustless AI, ReceiptOS-style verification work, or future provenance/semantic benchmark adapters.
