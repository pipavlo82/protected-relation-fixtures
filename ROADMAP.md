# Roadmap

## Current state

Protected Relation Fixtures is currently a benchmark seed / methodology nucleus.

It already contains:

- a core normative claim;
- fixture design principles;
- five canonical fixture cards;
- compact framing notes.

## Near-term next steps

1. **Stabilize canonical framing**
   - tighten fixture wording where needed;
   - keep the protected relation explicit in every fixture;
   - separate canonical docs from looser notes.

2. **Define a machine-readable fixture format**
   - fixture id;
   - weak observable;
   - protected relation;
   - expected fail-closed outcome;
   - minimal before/after object form.

3. **Add benchmark metadata**
   - scope tags (identity, relation-type, multiplicity, version-skew, composition);
   - expected evaluator behavior;
   - rationale for why weak observation still passes.

## Medium-term next steps

4. **Create canonical vectors/examples**
   - compact examples for each fixture;
   - before/after representations;
   - expected verifier output.

5. **Add adapters/tests**
   - small harnesses for exercising fixture expectations;
   - optional adapters for TSEI / Trustless AI / ReceiptOS-style evaluators.

6. **Add a benchmark summary doc**
   - comparison table of fixture classes;
   - what each class protects against;
   - how this lane complements transformation-stability methods.

## Boundaries

- This repo should not become a dumping ground for unrelated TSEI run artifacts.
- Frozen historical instances should remain in their original provenance locations.
- New claims should be added here only if they genuinely fit the protected-relation fixture lane.

## Longer-term possibility

If this seed proves useful, it can evolve into a reusable benchmark corpus for false-equivalence failures in semantic verification and provenance systems.
