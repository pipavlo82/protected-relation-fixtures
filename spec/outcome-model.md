# Outcome Model

**Status:** draft benchmark contract
**Purpose:** define semantic outcomes and observation states for protected-relation fixtures without collapsing everything into binary PASS/FAIL.

## 1. Why this exists

A protected-relation benchmark must distinguish at least three different kinds
of result:

1. the protected semantic relation is preserved;
2. the protected semantic relation is violated;
3. the protected semantic relation cannot be verified under the declared
   contract.

A binary PASS/FAIL model is too weak for fixtures involving version skew,
vocabulary loss, scope limitations, filtered data, or incomplete semantic
expressibility.

## 2. Semantic outcomes

Recommended semantic outcomes:

```text
PRESERVED
VIOLATED
UNVERIFIABLE
```

### 2.1 PRESERVED

Use `PRESERVED` when the evaluator can recompute the protected semantic object
and determine that:

```text
S0 =protected S1
```

under the declared protected relation policy.

### 2.2 VIOLATED

Use `VIOLATED` when the evaluator can recompute the protected semantic object
and determine that:

```text
S0 !=protected S1
```

under the declared protected relation policy.

### 2.3 UNVERIFIABLE

Use `UNVERIFIABLE` when the evaluator cannot legitimately decide preserved vs
violated under the declared contract.

This includes cases such as:

- loss of vocabulary needed to express the semantic state;
- scope limitations that prevent a warranted judgment;
- filtered or missing semantic inputs that are contract-relevant;
- downstream representations that still parse but do not preserve the protected
  status class.

`UNVERIFIABLE` is not a soft success. It is a fail-closed semantic state.

## 3. Observation-state model

In addition to semantic outcomes, the benchmark should allow a separate notion
of whether a given projection or observation was preserved.

Recommended observation states:

```text
true
false
unknown
```

For example:

```text
projection_preserved: true | false | unknown
protected_relation_preserved: true | false | unknown
```

## 4. Important separations

The following states must remain distinct when the contract distinguishes them:

```text
unknown
absent
empty
filtered-out
out-of-scope
```

These must not be silently collapsed.

In particular:

```text
unknown -> false
```

may be acceptable only if the contract says so explicitly.

But:

```text
unknown -> preserved
```

must never happen implicitly.

## 5. Canonical examples

### 5.1 Version-skew / unknown-member collapse

Upstream:

```text
UNVERIFIABLE(reason = X)
```

Downstream representation can no longer express `reason = X` exactly.

Correct semantic outcome:

```text
UNVERIFIABLE
```

not `PRESERVED` and not empty-success.

### 5.2 Local-only observation with global protected claim

A local projection may remain unchanged while the global protected relation is
not fully observable.

Correct semantic outcome:

```text
UNVERIFIABLE
```

unless the declared contract limits the claim to the local scope.

### 5.3 Exact semantic mismatch

A protected relation such as exact typed neighborhood identity can be directly
recomputed and shown to differ.

Correct semantic outcome:

```text
VIOLATED
```

## 6. Outcome vs benchmark result

Semantic outcome is not identical to benchmark pass/fail status.

Suggested interpretation:

- `PRESERVED` can support a PASS if the fixture expects preservation.
- `VIOLATED` can support a PASS if the fixture expects a hard negative.
- `UNVERIFIABLE` can support a PASS if the fixture expects fail-closed
  unverifiability.

Therefore benchmark evaluation needs both:

1. the semantic outcome produced by the evaluator;
2. the expected outcome class for the fixture.

## 7. Minimal machine-readable shape

The current schema/corpus lane should support something at least like:

```json
{
  "semantic_outcome": "UNVERIFIABLE",
  "projection_preserved": true,
  "protected_relation_preserved": "unknown",
  "reason_class": "version-skew-vocabulary-loss"
}
```

This is illustrative, not yet a frozen schema.

## 8. Practical evaluator rule

An evaluator must never treat a weaker observational success as if it were a
semantic preservation result.

If semantic preservation cannot be justified under the declared contract, the
correct result is:

```text
UNVERIFIABLE
```

or:

```text
VIOLATED
```

depending on what the fixture actually establishes.

## 9. Compact summary

The outcome model exists to stop the benchmark from collapsing into two bad
patterns:

```text
everything is PASS/FAIL only
```

and:

```text
anything not proven violated is treated as preserved
```

Protected-relation fixtures need a semantic model that can say:

- preserved
- violated
- unverifiable

without upgrading missing knowledge into semantic success.
