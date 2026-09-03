# Relation Discrimination v0

**Status:** additive draft hardening contract

**Identifier:** `relation-discrimination-v0`

**Purpose:** demonstrate that declared protected-relation policy distinctions are
semantically load-bearing over an independent synthetic witness basis.

## 1. Boundary

This contract is not a corpus rewrite, a v0 freeze, or an external adapter
contract. It does not change the bytes or meanings of the six seed fixtures,
their blind challenge views, the manifest, or the seed oracle.

The relation-discrimination suite is independent of:

- fixture `expected` fields;
- `corpus/v0/oracle/expected-results.json`;
- the seed-corpus `derive_semantic_result()` implementation; and
- assertion labels emitted by the seed-corpus gate.

Those artifacts cannot supply an expected result to this gate. The suite uses
only the policies, synthetic states, and expected matrix declared in
`conformance/relation-discrimination-v0/suite.json`.

## 2. Semantic relation

For a supported policy `R` and state `S`, the gate evaluates:

```text
Phi_R(S) -> canonical protected semantic object | UNVERIFIABLE
```

It then evaluates:

```text
Compare_R(Phi_R(S0), Phi_R(S1))
  -> PRESERVED | VIOLATED | UNVERIFIABLE
```

`Phi_R` selects the policy's justified scope, normalizes only explicitly
permitted identities and relation types, applies direction policy, applies
multiplicity policy, and produces a sorted semantic edge collection.

`Compare_R` returns:

- `PRESERVED` only when both extractions succeed and their canonical protected
  semantic objects are equal;
- `VIOLATED` only when both extractions succeed and those objects differ; or
- `UNVERIFIABLE` if either extraction cannot be justified.

The canonical object is an internal semantic comparison form. It is not a new
wire format and does not alter any corpus fixture.

## 3. Synthetic state model

Each synthetic state declares:

- `complete_scopes`: the exact scopes for which the state claims complete
  semantic information; and
- `relations`: relation records containing `source`, `relation_type`, `target`,
  and `scope`.

The marker `global` in `complete_scopes` warrants a global comparison. A
`local-bounded` policy instead requires its exact `scope_anchor` to be present
and ignores relations outside that boundary. Absence of the required
completeness marker is `UNVERIFIABLE`, never `PRESERVED`.

## 4. Supported policy values

The v0 discrimination evaluator supports only:

| Axis | Values |
|---|---|
| policy kind | `edge-relation` |
| identity | `anchored`, `alias-permitted` |
| relation type | `typed-exact`, `type-normalized`, `type-ignored` |
| multiplicity | `multiset-exact`, `set-collapsed` |
| direction | `directed-exact`, `direction-ignored` |
| scope | `global`, `local-bounded` |

Alias-permitted identity and type-normalized relation policies require explicit
maps. An undeclared alias or type is insufficient semantic information and
therefore yields `UNVERIFIABLE`. No guessed normalization is allowed.

An unsupported policy kind or value, malformed relation record, missing scope
claim, or incomplete semantic input also yields `UNVERIFIABLE`. Unknown policy
semantics must never be upgraded to `PRESERVED`.

## 5. Required discrimination axes

The suite requires exactly these five axes:

1. identity;
2. relation type;
3. multiplicity;
4. direction; and
5. scope.

Each declared policy pair must differ only in fields assigned to its named
axis. The gate runs every policy pair over the entire witness basis. At least
one declared required witness must produce different outcomes under the two
policies. Otherwise the gate fails with:

```text
UNRESOLVED_RELATION_DISCRIMINATION
```

The expected matrix covers both sides of every policy-pair/witness
combination. Missing matrix cells are rejected rather than inferred.

The initial basis includes direct separators for alias identity, normalized
relation type, duplicate-edge multiplicity, reversed direction, and
local-versus-global scope. It also includes a preserved positive control, an
undeclared alias, and an incomplete-global-scope case.

## 6. Separation matrix

A conforming run reports one status per required axis:

```text
identity: SEPARATED
relation_type: SEPARATED
multiplicity: SEPARATED
direction: SEPARATED
scope: SEPARATED
```

All five statuses must be `SEPARATED` for exit code 0. Missing axes, missing
required witnesses, non-isolated policy pairs, unclassified outcomes,
expectation mismatches, or unresolved separation cause a non-zero exit.

## 7. Mismatch taxonomy

The gate preserves security-significant distinctions:

| Expected | Evaluator | Classification |
|---|---|---|
| `VIOLATED` | `PRESERVED` | `UNSAFE_FALSE_PRESERVATION` |
| `UNVERIFIABLE` | `PRESERVED` | `UNSAFE_UNVERIFIABLE_UPGRADE` |
| `PRESERVED` | `VIOLATED` | `FALSE_VIOLATION` |
| `PRESERVED` | `UNVERIFIABLE` | `PRESERVATION_NOT_ESTABLISHED` |
| `VIOLATED` | `UNVERIFIABLE` | `VIOLATION_NOT_ESTABLISHED` |
| `UNVERIFIABLE` | `VIOLATED` | `UNVERIFIABLE_MISCLASSIFIED_AS_VIOLATION` |

Matching outcomes are classified as `MATCH`. Unknown outcome labels are
rejected and cannot enter a generic success path.

## 8. Mutation requirement

The test suite must demonstrate that the gate goes red when each required
semantic axis is independently collapsed. It must additionally reject a
missing required axis or witness, reject a mutated expected separation, keep
undeclared normalization fail-closed, and exercise the unsafe-upgrade
taxonomy.

Normative contract checks use explicit exceptions and `unittest` methods, not
Python `assert` statements, so `python -O` cannot remove them.

## 9. Non-goals

This layer does not:

- make the seed oracle authoritative for discrimination;
- change any existing fixture outcome;
- decide whether the corpus is frozen;
- validate a TSEI, RVR, ReceiptOS, or Trustless AI integration; or
- define the future external evaluator adapter interface.
