# Fixture 02 — Relation Type Changed, Shape Preserved

**Status:** private benchmark seed
**Lane:** protected-relation fixtures

## Fixture ID

`fixture-02-relation-type-loss`

## Core claim

Topology equality must not be treated as proof that the protected semantic
relation is preserved.

## Before

```text
owns(A, B)
```

## After

```text
depends_on(A, B)
```

## Weak observable that still passes

Examples of weak checks that may still PASS:

- same nodes appear
- same edge count
- same adjacency shape
- same endpoint pair `(A, B)`
- same coarse graph statistics for this edge

## What protected relation actually changes

The **meaning/type of the relation** changes.

The protected semantic object is not just "there is an edge" but "which
relation holds between these nodes".

## Why this fools weak observation

A weak projection that only preserves:

- connectivity
- cardinality
- endpoint pairing

can erase the distinction between semantically different relation types.

That loses the difference between:

```text
same shape
```

and

```text
same protected semantic relation
```

## Expected fail-closed result

If the verifier is supposed to protect relation semantics, then this fixture
must **fail closed**.

Expected conclusion:

```text
weak projection preserved = true
protected relation preserved = false
result = fail closed
```

## Minimal normative lesson

Same topology is not the same thing as the same relation.

## Why this matters

This is a canonical case where a graph or structured object can look unchanged
under a shape-only observer while the semantic claim being protected has
already changed.

## Candidate evaluation shape

A benchmark/evaluator should answer at least:

1. Was the weak projection preserved?  
   **Yes**
2. Was the protected relation preserved?  
   **No**
3. Is a PASS therefore allowed?  
   **No**

## Compact slogan

```text
same shape != same meaning
```
