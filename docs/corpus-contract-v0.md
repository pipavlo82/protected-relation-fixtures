# Corpus Contract v0

**Status:** draft corpus contract note

This document explains what the current `corpus/v0/` surface guarantees and what it does not.

## 1. Current representations

The repository currently distinguishes three roles:

1. **Full fixture object**
   - lives in `corpus/v0/cases/*.json`
   - contains the protected relation, before/after objects, listed projections, and expected semantic outcome

2. **Blind challenge view**
   - lives in `corpus/v0/challenge/cases/*.json`
   - strips answer-bearing fields such as `expected`, `metadata`, and self-reported projections
   - intended for TSEI-style or blind-evaluation settings where the challenge surface must not carry the oracle directly

3. **Oracle view**
   - lives in `corpus/v0/oracle/expected-results.json`
   - binds the expected semantic outcomes for the current seed corpus

## 2. What is currently guaranteed

At `v0`, the repository now guarantees at least:

- every seed case has a machine-readable full fixture object;
- every seed case has a detached blind challenge representation;
- every seed case is bound in `manifest.json` by SHA-256;
- the oracle file is separately bound by SHA-256;
- seed integrity is checked mechanically;
- seed projection claims are recomputed for the current five fixture vectors;
- fixture id / filename / manifest-entry consistency is checked mechanically.

## 3. Byte format requirement

The current corpus binds exact bytes through manifest digests.

The current requirement should be read as a **byte-format requirement**, not yet as a fully independent canonical JSON derivation contract.

At present, the repository relies on exact stored bytes plus SHA-256 digests, together with UTF-8 JSON and exactly one final LF. A stronger fully specified canonical serializer contract may be added later.

## 4. What is not yet claimed

The current corpus contract does **not** yet claim:

- fully frozen canonical JSON derivation from prose alone;
- full semantic recomputation for every possible future fixture class;
- final adapter/test coverage for every external verifier implementation;
- that the current seed corpus is already the final benchmark closure.

## 5. Why this distinction matters

The benchmark is intended to support fail-closed evaluation. That requires a clean distinction between:

- the object being challenged,
- the oracle that defines the expected semantic result,
- and the integrity layer that binds exact bytes.

Without that split, a public machine-readable corpus can accidentally leak its own answers into the challenge surface.
