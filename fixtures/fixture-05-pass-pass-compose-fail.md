# Fixture 05 — Pass, Pass, Compose, Fail

**Status:** private benchmark seed
**Lane:** protected-relation fixtures

## Fixture ID

`fixture-05-pass-pass-compose-fail`

## Core claim

Per-step admissibility must not be treated as proof of compositional semantic
safety.

## Before

Initial state `S0` satisfies the protected relation.

Two transformations are available:

- `T1`
- `T2`

Each is individually considered admissible under a local or per-step check.

## After

- `T1(S0)` passes the admissibility check.
- `T2(S1)` passes the admissibility check, where `S1 = T1(S0)`.
- But the composition `T2(T1(S0))` breaks the protected semantic relation.

## Weak observable that still passes

Examples of weak checks that may still PASS:

- each transform individually satisfies local rules
- each transform individually preserves a narrow projection
- no single step triggers the local fail condition

## What protected relation actually changes

The **composed semantic object** is no longer valid, even though each step
looked individually admissible.

The failure exists at the composition level, not necessarily at either step in
isolation.

## Why this fools weak observation

A weak observer can confuse:

- local step safety
- with
- global compositional safety

That loses the distinction between:

```text
each step passes
```

and

```text
the composed result preserves the protected relation
```

## Expected fail-closed result

If the protected relation must survive the full composed pipeline, this fixture
must **fail closed** at the composition level.

Expected conclusion:

```text
T1 admissible = true
T2 admissible = true
composed protected relation preserved = false
result = fail closed
```

## Minimal normative lesson

Pass plus pass does not imply pass after composition.

## Why this matters

This fixture protects against systems that overlearn a per-step discipline and
then silently assume that composition preserves the same guarantees.

It is especially relevant whenever a methodology claims stability across a
transformation graph rather than a single isolated edge.

## Candidate evaluation shape

A benchmark/evaluator should answer at least:

1. Did `T1` pass the local admissibility check?  
   **Yes**
2. Did `T2` pass the local admissibility check?  
   **Yes**
3. Did the composed result preserve the protected relation?  
   **No**
4. Is a PASS therefore allowed?  
   **No**

## Compact slogan

```text
pass + pass != composition-safe
```
