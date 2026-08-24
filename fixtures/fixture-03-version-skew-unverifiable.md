# Fixture 03 вЂ” Version Skew / Unknown-Member Collapse

**Status:** benchmark seed
**Lane:** protected-relation fixtures

## Fixture ID

`fixture-03-version-skew-unverifiable`

## Core claim

Loss of representational granularity must not be treated as permission to
upgrade a protected semantic state.

## Before

Upstream state is effectively:

```text
UNVERIFIABLE(reason = X)
```

where `X` is a specific reason/member/justification known upstream.

## After

A downstream representation still parses, but its vocabulary no longer has a
way to represent `reason = X` exactly.

## Weak observable that still passes

Examples of weak checks that may still PASS:

- downstream object/schema still parses
- a status field is still present
- partial structural compatibility remains
- transport/re-encoding succeeds

## What protected relation actually changes

The downstream system loses the ability to preserve the exact protected
semantic state.

The correct protected state is still:

```text
UNVERIFIABLE
```

not success, not verified, not empty-reason acceptance.

## Why this fools weak observation

A weak observer can collapse:

- unknown
- absent
- empty
- downgraded reason vocabulary

into a false appearance of compatibility or success.

That erases the difference between:

```text
still parseable
```

and

```text
still semantically preservable
```

## Expected fail-closed result

If the protected relation includes the distinction between verifiable and
unverifiable status, then this fixture must remain fail-closed at the semantic
layer.

Expected conclusion:

```text
weak projection preserved = true
protected relation preserved = false
result = remain UNVERIFIABLE / fail closed
```

## Minimal normative lesson

Unknown is not success.

## Why this matters

This is a strong real-world class because it arises naturally from version-skew
and vocabulary drift, not only from synthetic benchmark construction.

It protects against a dangerous upgrade path where loss of reason granularity
silently mints a stronger conclusion.

## Candidate evaluation shape

A benchmark/evaluator should answer at least:

1. Does the downstream object still parse?  
   **Yes**
2. Can it still preserve the exact protected semantic status?  
   **No**
3. Is a stronger semantic outcome therefore allowed?  
   **No**

## Compact slogan

```text
unknown != ok
```

