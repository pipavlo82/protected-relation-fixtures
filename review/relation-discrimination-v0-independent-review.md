# Relation Discrimination v0 Second-Implementation Review

## Review identity

- Reviewed PR: `#4`
- Reviewed PR head: `b14d63e0d8f869c0b7aa0efdb1d2a0a23ed6dd68`
- Reviewed base: `154d35d0a4748da2ef40332e310a01d1549948fa`
- PR merge commit: `5061c6bbdc6738c72d37e73aa0cff8f7811d2b43`
- Review mode: `NON_BLIND_SECOND_IMPLEMENTATION`
- Review verdict: `REPRODUCED`

The review was explicitly non-blind because the reviewer had inspected the
candidate implementation during an earlier task. The second evaluator was
nevertheless separately implemented from the declared specification and suite.
It did not import, call, or use helper logic from the candidate evaluator.

## Frozen evidence

| Artifact | SHA-256 |
|---|---|
| `review/relation_discrimination_independent.py` | `1d8adf8e502484ab462f06cd6bd2c3eb2ca1d76bf61cc849b9f9c093c3dd4cc6` |
| `review/relation-discrimination-independent-first-run.json` | `b918fd86b3ebd68b22dd92241e03194162dfab04effc37bca0d69550b2674510` |
| `review/relation-discrimination-independent-negative-controls.json` | `edd7daf99df34600ce9ac29d6a610405eec2a414e2524c45fb0c6b93fb5bd5e1` |

The first-run artifact was written before the candidate implementation was
reopened for the final conceptual comparison. It records all 80 policy-pair ×
witness × side outcomes.

## Results

- Semantic outcomes matched: `80/80`
- Candidate-versus-review semantic mismatches: `0/80`
- Required policy axes separated: `5/5`
- Independent negative controls passed: `11/11`
- Identity collapse: detected
- Relation-type collapse: detected
- Multiplicity collapse: detected
- Direction collapse: detected
- Scope collapse: detected
- Missing required witness: rejected
- Unsupported policy value: `UNVERIFIABLE`
- Undeclared identity alias: `UNVERIFIABLE`
- Incomplete global scope: `UNVERIFIABLE`
- Expected `VIOLATED`, actual `PRESERVED`:
  `UNSAFE_FALSE_PRESERVATION`
- Expected `UNVERIFIABLE`, actual `PRESERVED`:
  `UNSAFE_UNVERIFIABLE_UPGRADE`

The separating witnesses were:

- identity: `identity-alias`, `undeclared-alias`;
- relation type: `relation-type-normalization`;
- multiplicity: `multiplicity-collapse`;
- direction: `direction-reversal`; and
- scope: `scope-outside-drift`, `incomplete-global-scope`.

## Authority boundary

> Two separately implemented evaluators reproduce the declared
> relation-discrimination contract over the exact synthetic witness suite.

This is the strongest claim established by the review. It is not a claim that
the protected semantics are objectively correct for every external domain.

> The synthetic witness construction, alias maps, scope declarations, and
> completeness markers remain declared benchmark inputs. Agreement between two
> implementations does not independently establish that those declarations
> correctly model every external domain.

Both implementations treat the literal `global` marker as the suite's
completeness assertion and trust the declared relation scope labels. A
local-bounded policy intentionally excludes relations outside its scope. The
legitimacy of those declarations remains outside this reproduction result.

## Boundaries

This review evidence does not:

- modify production relation-discrimination semantics or its suite;
- modify corpus cases, challenge views, manifest, oracle, or fixture schema;
- validate an external adapter or downstream integration;
- amend the merged PR #4 history; or
- make a v0 freeze decision.
