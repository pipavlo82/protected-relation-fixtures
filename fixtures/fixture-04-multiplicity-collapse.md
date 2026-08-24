# Fixture 04 — Multiplicity Collapse

**Status:** private benchmark seed
**Lane:** protected-relation fixtures

## Fixture ID

`fixture-04-multiplicity-collapse`

## Core claim

Set-level equality must not be treated as proof that multiplicity-sensitive
protected semantics are preserved.

## Before

Conceptually, node `A` has two semantically distinct justified links to `B`.
For example:

```text
A -> B
A -> B
```

where the duplication is meaningful, not redundant.

## After

The downstream representation preserves only one relation:

```text
A -> B
```

## Weak observable that still passes

Examples of weak checks that may still PASS:

- same neighbor set `{B}`
- same endpoint pair `(A, B)`
- same coarse adjacency shape
- same boolean fact "A is connected to B"

## What protected relation actually changes

The protected semantic object changes because multiplicity / cardinality /
repeated justified linkage is no longer preserved.

The difference is not in whether `B` appears at all, but in **how many
meaningful links** exist and whether that multiplicity matters to the contract.

## Why this fools weak observation

A weak observer can collapse multiset semantics into set semantics.

That loses the distinction between:

```text
B appears
```

and

```text
B appears with multiplicity 2
```

If the protected relation is multiplicity-sensitive, then that collapse is a
semantic loss, not a harmless normalization.

## Expected fail-closed result

If multiplicity is part of the protected relation, this fixture must **fail
closed**.

Expected conclusion:

```text
weak projection preserved = true
protected relation preserved = false
result = fail closed
```

## Minimal normative lesson

Set equality is not multiset equality.

## Why this matters

This fixture protects against false PASS results where a verifier says the
relationship is preserved simply because at least one edge remains, while the
actual contract required multiplicity-sensitive preservation.

## Candidate evaluation shape

A benchmark/evaluator should answer at least:

1. Was the weak set-like projection preserved?  
   **Yes**
2. Was the multiplicity-sensitive protected relation preserved?  
   **No**
3. Is a PASS therefore allowed?  
   **No**

## Compact slogan

```text
same set != same multiplicity
```
