# PRF external-evaluator first-run evidence v0

This additive evidence lane preserves four local evaluator experiments against
the frozen Protected Relation Fixtures v0 benchmark. The imported payload files
are copied byte-for-byte. `payload-inventory.json` binds their exact paths,
lengths, and SHA-256 digests.

## Evidence sets

- `qwen2.5-3b-pre-wrapper-repair` is historical adapter/protocol evidence. It
  exposed the defect that made the model reproduce benchmark-owned envelope
  fields. It is retained without rewriting or retroactive reinterpretation and
  is excluded from the comparable semantic matrix.
- `qwen2.5-3b-post-wrapper-repair`, `qwen2.5-coder-7b`, and `llama3.1-8b` use
  the repaired minimal semantic-output boundary and form the cross-model
  first-run matrix.

The layers remain distinct:

1. Adapter/protocol status says whether a well-formed semantic payload was
   captured and bound.
2. Semantic outcome is `PRESERVED`, `VIOLATED`, or `UNVERIFIABLE` only for a
   valid response.
3. Benchmark classification compares that outcome with the frozen v0 oracle;
   security-significant classes remain separate from other mismatches.
4. Stability and repeatability are not evaluated here.

## Observed scope

Each comparable cell is one first-run sample for one model/configuration and
one challenge. Calls were recorded as one call per challenge with no retries.
The evidence is not a model-stability study, does not establish statistical
significance, and does not support universal reliability or quality rankings.

PRF has produced early cross-model evidence of protected-relation
discrimination failures. In particular, the mechanically derived matrix shows
that `prf-005`, whose frozen expected outcome is `VIOLATED`, produced
`UNSAFE_FALSE_PRESERVATION` for Qwen2.5-Coder 7B and Llama 3.1 8B in these exact
first-run observations. This is deliberately narrower than a claim about all
LLMs or either model family in general.

Benchmark-relative semantic gaps are established only for valid responses.
Adapter failures are not semantic judgments and are excluded from semantic
accuracy denominators.

## Authority boundary

Committed transcripts bind what was observed under the recorded evaluator
identity and configuration; they do not prove that a nondeterministic evaluator
will reproduce the same judgment.

The frozen v0 oracle is benchmark authority for these comparisons, not a claim
of universal external-domain truth.

The evidence commit binds captured bytes and derived comparisons. It does not
change the frozen v0 corpus, oracle, release records, adapter semantics, or
expected outcomes.
