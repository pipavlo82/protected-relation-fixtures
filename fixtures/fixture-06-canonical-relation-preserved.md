# Fixture 06 — Raw representation changed, canonical relation preserved

**Status:** benchmark seed  
**Lane:** protected-relation fixtures

## Fixture ID

`prf-006`

## Core claim

Raw representation inequality must not imply that the protected semantic relation changed.

## Before and after

The raw source identifier, target identifier, and relation spelling change across the transformation. Under the fixture's declared alias and type-normalization policy, both representations resolve to the same canonical directed relation:

```text
alice --owns--> document-A
```

## Expected result

```text
raw projection preserved = false
canonical protected relation preserved = true
semantic outcome = PRESERVED
fail closed required = false
```

## Why this control matters

The negative fixtures prevent false equivalence. This mirror-positive fixture prevents the opposite error: rejecting a legitimate representation change when the declared canonical protected relation is unchanged.

## Minimal normative lesson

Compare the protected relation under its declared equivalence policy; do not substitute raw byte or identifier equality for semantic comparison.
