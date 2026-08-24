# Protected Relation Fixtures вЂ” One-Page Note

**Status:** research note
**Purpose:** compact framing for a future benchmark family where weak observational equality is not allowed to stand in for protected semantic equality.

## Core normative claim

> Equality under a weak observation must not imply equivalence of the protected semantic relation.

Operational version:

> Do not trust a preserved projection; recompute the protected semantic object and compare that instead.

## Why this matters

A system can preserve weak observables such as counts, degrees, adjacency shape,
or partial endpoint outputs while still changing the semantic object that the
contract actually protects.

The benchmark family should therefore distinguish:

- observational preservation
- semantic preservation
- provenance / identity preservation

## Five canonical fixtures

### 1. Local neighborhood preserved, global identity changed
- Weak observable passes: degree, local edge count
- Protected relation changes: exact neighborhood identity
- Fail-closed lesson: local equality is not enough

### 2. Relation-type changed, shape preserved
- Weak observable passes: same nodes, same adjacency shape
- Protected relation changes: edge meaning (`owns` vs `depends_on`)
- Fail-closed lesson: topology equality is not semantic equality

### 3. Multiplicity collapse
- Weak observable passes: same set of neighbors
- Protected relation changes: multiplicity / repeated justified links
- Fail-closed lesson: set equality is not multiset equality

### 4. Unknown-member / version-skew collapse
- Weak observable passes: downstream representation still parses
- Protected relation changes: upstream `UNVERIFIABLE(reason=X)` loses the exact reason vocabulary
- Fail-closed lesson: loss of granularity must not upgrade `UNVERIFIABLE` to success

### 5. Pass-pass-compose-fail
- Weak observable passes: each single transform looks admissible
- Protected relation changes: the composition breaks the semantic object
- Fail-closed lesson: per-step safety does not imply compositional safety

## Compact table

| Fixture | Weak observable that still passes | Protected relation that changes | Expected result |
|---|---|---|---|
| Local neighborhood preserved, global identity changed | degree / local count | semantic neighborhood identity | fail closed |
| Relation-type changed, shape preserved | same topology | relation meaning | fail closed |
| Multiplicity collapse | same set membership | multiplicity/cardinality | fail closed |
| Unknown-member / version-skew collapse | parseable downstream status | exact protected semantic state | remain `UNVERIFIABLE` |
| Pass-pass-compose-fail | per-step admissibility | composed semantic relation | fail closed |

## Design principle

The benchmark must always make the protected relation explicit. Otherwise the
same artifact pair can be read as either equivalent or non-equivalent under
informal interpretation drift.

## Research direction

This looks like a promising benchmark / methodology lane for TSEI, Trustless AI,
or ReceiptOS-style verification work, but it should remain separate from the
currently frozen authority-run lanes.

