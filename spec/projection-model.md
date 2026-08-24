# Projection Model

**Status:** draft benchmark contract
**Purpose:** define weak observational projections and their relationship to protected semantic relations.

## 1. Why this exists

The central benchmark question in this repository is not simply whether two
states differ.

It is whether a verifier confuses:

```text
preserved weak observation
```

with:

```text
preserved protected semantic relation
```

To make that measurable, the repository needs an explicit projection model.

## 2. Projection vs protected relation

A projection is any weaker observational summary derived from a state.

Notation:

```text
P(S)
```

means “the projection of state `S` under projection `P`”.

A fixture becomes interesting when:

```text
P(S0) = P(S1)
```

but:

```text
S0 !=protected S1
```

The projection model therefore exists to make clear:

- which weak views are preserved;
- which semantic object is not preserved;
- where a verifier should fail closed.

## 3. Suggested projection ladder

A useful starting ladder is:

```text
P0 = edge existence
P1 = local degree
P2 = full degree vector
P3 = typed in/out degree
P4 = neighborhood histogram
P5 = bounded-k neighborhood
P6 = motif / local structural summary
P7 = endpoint output
R  = protected semantic relation
```

This ladder is not yet a frozen ontology. It is a practical starting framework.

## 4. Projection meanings

### P0 — edge existence
Weakest view: does some edge/relation exist at all?

### P1 — local degree
A node-local count such as `degree(A) = 6`.

### P2 — full degree vector
Degree preserved for every node in the declared universe.

### P3 — typed in/out degree
Degree counts split by type or direction.

### P4 — neighborhood histogram
A local frequency summary over neighbor classes or relation classes.

### P5 — bounded-k neighborhood
A bounded local neighborhood (e.g. one-hop or two-hop) captured explicitly.

### P6 — motif / local structural summary
A stronger local pattern summary, still weaker than a full protected relation.

### P7 — endpoint output
A downstream output or decision surface that may remain unchanged even while
protected semantics drift underneath.

### R — protected semantic relation
The semantic object that the contract actually protects.

## 5. Benchmark use

Each serious fixture should identify at least:

- which projections remain preserved;
- whether the protected relation is preserved or not;
- whether a fail-closed result is expected.

Illustrative machine-readable shape:

```json
{
  "preserved_projections": ["P1", "P2"],
  "broken_at": "protected_relation"
}
```

This is illustrative, not yet a frozen schema.

## 6. Important warning

Projection preservation is not cumulative proof of semantic preservation.

For example, preserving:

- edge count,
- degree,
- degree vector,
- and even bounded local structure

still does not by itself prove:

```text
S0 =protected S1
```

The protected semantic relation must be recomputed under its own policy.

## 7. Example interpretations

### Local neighborhood identity fixture

Possible evaluation:

```text
P1 preserved = true
P2 preserved = false or true depending on construction
R preserved = false
```

### Relation-type-loss fixture

Possible evaluation:

```text
P0 preserved = true
P1 preserved = true
shape-like projections preserved = true
R preserved = false
```

### Version-skew fixture

Possible evaluation:

```text
parseability-like projection preserved = true
status-slot presence preserved = true
R preserved = unknown / false under contract
semantic outcome = UNVERIFIABLE
```

## 8. Why the ladder matters

The ladder enables a stronger research question:

> At what observational strength does a discriminator stop confusing preserved projection with preserved semantics?

That makes the corpus more than a bag of examples. It turns it into a possible
measurement surface for evaluator behavior.

## 9. Non-goals

This document does not yet define:

- the final set of projection ids;
- the final machine-readable encoding;
- how every projection is recomputed for every domain;
- whether all fixture classes need every projection populated.

Those can be refined in later schema/corpus work.

## 10. Practical rule

A verifier should never be allowed to claim semantic preservation solely because
some lower projection rung remained constant.

The safe rule is:

```text
preserved projection != preserved protected semantics
```

unless the protected relation policy explicitly collapses them.

## 11. Compact summary

The projection model exists so the benchmark can say, rigorously:

- what weaker views stayed the same;
- what stronger semantic object changed;
- and why a fail-closed evaluator must refuse to overclaim equivalence.
