# Fixture 01 — Local Neighborhood Preserved, Global Identity Changed

**Status:** private benchmark seed
**Lane:** protected-relation fixtures

## Fixture ID

`fixture-01-local-neighborhood-identity`

## Core claim

A preserved local projection must not be treated as proof that the protected
semantic neighborhood is preserved.

## Before

Node `A` is connected to:

```text
{B, C, D, E, F, G}
```

## After

Node `A` is connected to:

```text
{B, C, D, H, I, J}
```

## Weak observable that still passes

Examples of weak checks that may still PASS:

- `degree(A) = 6`
- same local edge count
- same coarse cardinality of the neighborhood
- same count-shaped summary over the immediate adjacency

## What protected relation actually changes

The **identity of the protected semantic neighborhood** changes.

Even if the local count is preserved, the exact neighborhood is no longer the
same semantic object.

## Why this fools weak observation

A weak projection can collapse:

- exact neighbor identity
- semantic membership
- set replacement under equal cardinality

into a count-only observation.

That loses the distinction between:

```text
same number of neighbors
```

and

```text
same protected neighborhood
```

## Expected fail-closed result

If the verifier is supposed to protect exact semantic neighborhood identity,
then this fixture must **fail closed**.

Expected conclusion:

```text
weak projection preserved = true
protected relation preserved = false
result = fail closed
```

## Minimal normative lesson

Local neighborhood equality must not imply global neighborhood identity.

## Why this matters

This is the simplest canonical example of a benchmark where:

- observational preservation exists,
- semantic preservation does not,
- and a verifier that trusts only local counts produces a false PASS.

## Candidate evaluation shape

A benchmark/evaluator should answer at least:

1. Was the weak projection preserved?  
   **Yes**
2. Was the protected semantic neighborhood preserved?  
   **No**
3. Is a PASS therefore allowed?  
   **No**

## Compact slogan

```text
same degree != same neighborhood
```
