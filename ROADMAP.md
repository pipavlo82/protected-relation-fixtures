# Roadmap

## Current state

Protected Relation Fixtures is currently a local contract-closure candidate for its v0 benchmark seed.

It already contains:

- a core normative claim;
- fixture design principles;
- six canonical fixture vectors, including one mirror-positive control;
- a machine-readable Draft 2020-12 schema;
- exact-byte manifest and oracle bindings;
- detached challenge derivation;
- projection and semantic recomputation for every current vector;
- negative tests that remain active under `python -O`;
- a GitHub Actions validation workflow.

## Near-term next steps

1. **Independent exact-diff review**
   - review the v0 fixture and schema changes;
   - reproduce all validation commands from a clean checkout;
   - verify manifest and oracle bytes independently.

2. **Freeze decision**
   - decide whether the reviewed bytes become the first frozen v0 corpus release;
   - record the exact commit, tree, manifest digest, and validator environment;
   - do not call the current local candidate frozen before that decision.

3. **External adapter contract**
   - define how an external evaluator consumes challenge inputs without oracle leakage;
   - keep adapter outcomes separate from corpus integrity;
   - require fail-closed behavior for unsupported future fixture classes.

## Medium-term next steps

4. **Add external adapters and conformance tests**
   - optional adapters for TSEI / Trustless AI / ReceiptOS-style evaluators;
   - require adapters to report unsupported classes rather than infer an answer;
   - preserve the challenge/oracle separation.

5. **Add a benchmark summary doc**
   - comparison table of fixture classes;
   - what each class protects against;
   - how this lane complements transformation-stability methods.

## Boundaries

- This repo should not become a dumping ground for unrelated TSEI run artifacts.
- Frozen historical instances should remain in their original provenance locations.
- New claims should be added here only if they genuinely fit the protected-relation fixture lane.

## Longer-term possibility

If this seed proves useful, it can evolve into a reusable benchmark corpus for false-equivalence failures in semantic verification and provenance systems.
