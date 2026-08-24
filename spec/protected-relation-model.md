# Protected Relation Model

**Status:** draft benchmark contract
**Purpose:** define what it means for a fixture to preserve or violate a protected semantic relation, independently of weaker observational projections.

## 1. Core rule

A fixture in this repository is not primarily about whether two representations
are textually different.

It is about whether:

```text
S0 =protected S1
```

or

```text
S0 !=protected S1
```

under an explicitly declared protected relation.

Normative rule:

> Equality under a weak observation must not imply equivalence of the protected semantic relation.

Operational rule:

> Do not trust a preserved projection; recompute the protected semantic object and compare that instead.

## 2. Required distinction

Every serious fixture in this corpus should distinguish at least three layers:

1. **raw representation**
2. **weak observation / projection**
3. **protected semantic relation**

This means the following implications are all invalid by default unless a
fixture or policy explicitly states otherwise:

```text
Raw(S0) = Raw(S1)  =>  S0 =protected S1
Raw(S0) != Raw(S1) =>  S0 !=protected S1
P(S0) = P(S1)      =>  S0 =protected S1
```

where `P` is any weak projection or observational summary.

## 3. Protected relation

A protected relation is the semantic equivalence policy that the fixture expects
an evaluator to preserve, violate, or leave unverifiable.

At minimum, a protected relation definition should include the following fields.

### 3.1 Required fields

```text
protected_relation
identity_policy
relation_type_policy
multiplicity_policy
direction_policy
scope
universe
equivalence_policy
policy_version
```

### 3.2 Field meanings

#### `protected_relation`
The semantic object being protected.

Examples:

- exact typed neighborhood
- identity partition
- multiplicity-sensitive edge set
- directed authorization relation
- verifier status class

#### `identity_policy`
Defines whether node/object identity is protected.

Examples:

- `anchored`
- `alias-permitted`
- `automorphism-tolerant`
- `partition-sensitive`

#### `relation_type_policy`
Defines whether relation labels/types are protected.

Examples:

- `typed-exact`
- `type-normalized`
- `type-ignored`

#### `multiplicity_policy`
Defines whether repeated semantic links matter.

Examples:

- `multiset-exact`
- `set-collapsed`
- `count-preserving`

#### `direction_policy`
Defines whether direction is protected.

Examples:

- `directed-exact`
- `undirected`
- `direction-ignored`

#### `scope`
Defines the region of the object graph / state space that the claim is about.

Examples:

- exact neighborhood of `A`
- bounded-k neighborhood around `A`
- full graph
- status field only

#### `universe`
Defines the domain over which semantic comparison is valid.

Examples:

- declared node set
- declared edge set
- complete case universe
- all members visible as of a given state snapshot

#### `equivalence_policy`
Defines the semantic rule for deciding whether two states are protected-equivalent.

Examples:

- exact equality
- partition-preserving equivalence
- normalized typed equality
- status-preserving equivalence

#### `policy_version`
Stable version identifier for the protected relation contract.

## 4. What can differ while semantics remain preserved

A fixture must allow for the possibility that raw representation changes while
protected semantics remain the same.

Examples of differences that may be representation-level only:

- alias substitution
- permitted identifier renaming
- benign normalization
- serialization key reordering
- equivalent relation syntax
- automorphism-equivalent rewrites, when identity is not protected

Therefore this corpus must support mirror-positive fixtures where:

```text
Raw(S0) != Raw(S1)
```

but:

```text
S0 =protected S1
```

## 5. What can stay observationally equal while semantics drift

A fixture must also support the opposite and more dangerous class:

```text
P(S0) = P(S1)
```

while:

```text
S0 !=protected S1
```

Examples:

- same degree, different neighborhood identity
- same adjacency shape, different relation type
- same neighbor set, different multiplicity
- same parseability, different protected status class
- same local admissibility, unsafe composition

## 6. Outcome expectations

The protected relation model does not force a binary PASS/FAIL world.

A fixture should be compatible with at least these semantic outcomes:

```text
PRESERVED
VIOLATED
UNVERIFIABLE
```

This is especially important when a downstream representation cannot faithfully
express the upstream protected semantic state.

Example:

```text
UNVERIFIABLE(reason = X)
```

must not be silently upgraded to `PRESERVED` merely because `reason = X` can no
longer be represented downstream.

## 7. Scope discipline

A local claim is not the same thing as a global claim.

The model must preserve the distinction between:

```text
not observed
observed unchanged
globally unchanged
```

A fixture should therefore make clear whether the protected relation is:

- local
- scoped
- global
- bounded by a declared universe

## 8. Minimal machine-readable shape

The current schema/corpus lane should be able to represent at least this shape:

```json
{
  "protected_relation": {
    "kind": "exact_typed_neighborhood",
    "identity_policy": "anchored",
    "relation_type_policy": "typed-exact",
    "multiplicity_policy": "multiset-exact",
    "direction_policy": "directed-exact",
    "scope": ["A"],
    "universe": "declared_fixture_universe",
    "equivalence_policy": "exact",
    "policy_version": "v0"
  }
}
```

This is illustrative, not yet a frozen schema.

## 9. Benchmark implications

A verifier should not be evaluated only on whether it detects arbitrary
representation changes.

It should be evaluated on whether it correctly distinguishes:

- preserved weak projection vs preserved protected semantics
- preserved raw meaning vs changed raw text
- semantic violation vs semantic unverifiability

This repository therefore needs both:

- negative fixtures: observational equality with semantic drift
- positive fixtures: representational drift with semantic preservation

## 10. Non-goals

This model does not yet define:

- the final machine-readable schema
- the final oracle/result format
- the projection ladder in full detail
- the full corpus manifest contract

Those belong in companion specs such as:

- `outcome-model.md`
- `projection-model.md`
- `fixture-schema.v0.json`
- corpus manifest specifications

## 11. Practical test for every fixture

Before treating a fixture as serious, ask:

1. What is the protected relation?
2. Is identity protected, normalized, or ignorable?
3. Are relation types protected?
4. Is multiplicity protected?
5. Is direction protected?
6. What is the exact scope?
7. What is the declared universe?
8. Under what policy are `before` and `after` considered semantically equal?

If these cannot be answered, the fixture is still illustrative, not yet a
rigorous benchmark element.

## 12. Compact summary

A protected relation model exists to stop a benchmark from collapsing into one
of two bad simplifications:

```text
any raw difference => fail
```

or:

```text
any preserved weak projection => pass
```

This repository is about the harder middle ground:

```text
recompute the semantic object
then compare under an explicit protected relation policy
```
