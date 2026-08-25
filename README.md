# Protected Relation Fixtures

Protected Relation Fixtures is a benchmark corpus for cases where weak observational equality is preserved while the protected semantic relation is not. It is designed for fail-closed verifiers, provenance systems, and transformation-stability methods that must distinguish count/shape preservation from actual semantic preservation.

## Core normative claim

> Equality under a weak observation must not imply equivalence of the protected semantic relation.

Operational version:

> Do not trust a preserved projection; recompute the protected semantic object and compare that instead.

## Canonical visual formulations

### Core negative class

```text
P(S0) = P(S1)
while
S0 !=protected S1
```

### Core mirror-positive class

```text
Raw(S0) != Raw(S1)
while
S0 =protected S1
```

### Operational rule

```text
preserved projection
!=
preserved protected semantics
```

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
- a claim that every fixture here already has a fully frozen canonical vector contract;
- a substitute for independently recomputing the protected semantic object.

## Current canonical fixture set

1. **Local neighborhood preserved, global identity changed**
2. **Relation type changed, shape preserved**
3. **Version skew / unknown-member collapse**
4. **Multiplicity collapse**
5. **Pass, pass, compose, fail**
6. **Raw representation changed, canonical relation preserved**

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
  LICENSE
  CITATION.cff
  docs/
    core-claim.md
    fixture-design-principles.md
    visual-formulations.md
    corpus-contract-v0.md
  spec/
    protected-relation-model.md
    outcome-model.md
    projection-model.md
    fixture-schema.v0.json
  corpus/
    v0/
      manifest.json
      cases/
      challenge/
      oracle/
  fixtures/
    fixture-01-local-neighborhood-identity.md
    fixture-02-relation-type-loss.md
    fixture-03-version-skew-unverifiable.md
    fixture-04-multiplicity-collapse.md
    fixture-05-pass-pass-compose-fail.md
    fixture-06-canonical-relation-preserved.md
  tools/
    derive_challenge_views.py
    validate_manifest.py
    validate_seed_corpus.py
  tests/
    test_manifest_and_seed_corpus.py
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

Current state: **local contract-closure candidate for the v0 seed corpus**.

The repository now carries six machine-readable fixtures, including a mirror-positive control. The local validation path enforces exact stored-byte requirements, manifest and oracle digests, Draft 2020-12 schema conformance, detached challenge views, projection recomputation, and seed semantic recomputation against both the fixture expectations and oracle. The same negative suite runs under normal Python and `python -O`, and CI executes both modes.

This remains a review candidate, not a frozen release. The current recomputers cover the declared v0 fixture classes; future classes require an explicit recomputation rule and tests before entering the manifest.

## Local verification

```text
python -m pip install -r requirements-dev.txt
python tools/validate_manifest.py
python tools/validate_seed_corpus.py
python -m unittest discover -s tests -v
python -O -m unittest discover -s tests -v
```

## Relation to TSEI, ReceiptOS, and Chronicle-style systems

- **TSEI**: this repo is a pressure-test lane for cases where preserved projections can tempt a verifier into overclaiming preserved semantics.
- **ReceiptOS**: this repo can serve as an adversarial fixture corpus for independently recomputable receipt/verifier paths that must fail closed on false equivalence.
- **Chronicle-style systems**: this repo is relevant wherever ordered event continuity or observable stability can be misread as preserved semantic identity.

In short: this repo is not a replacement for those systems. It is a benchmark layer for testing whether they distinguish weak observational preservation from actual protected semantic preservation.

## Why keep this separate

This repo is intentionally separate from any single TSEI run lane or overloaded product repository. The point is to give protected-relation fixtures their own identity so they can be reused across TSEI, Trustless AI, ReceiptOS-style verification work, or future provenance/semantic benchmark adapters.
