# InvinoVeritas v18 epistemic-basis commitment case study

This additive, post-v0 evidence lane applies Protected Relation Fixtures
reasoning to the InvinoVeritas v18 `epistemic_basis` decision commitment. It is
not a frozen-v0 fixture and does not modify or reinterpret frozen v0.

The weak projection `verdict == "reject"` collapses two distinct semantic
states: `reject/evidence_against` and `reject/insufficient_evidence`. The second
order question is whether exposing that distinction in a response is equivalent
to preserving it in the signed decision commitment. It is not.

The captured v18 production proof names `epistemic_basis` in its stored
`decision_ref_preimage_fields`. Its stored rule requires every listed key to be
present in the hashed object and represents an absent optional value as JSON
`null`. The original proof verifies. A local copy that changes only
`epistemic_basis` from `null` to `evidence_against`, without changing the stored
event ID, signature, or `decision_ref`, fails public verification and reports
`decision_ref_recomputes == false`.

Ledger entry 260 is a v17 compatibility control. Its own stored preimage field
list does not contain `epistemic_basis`, and it verifies under that stored
contract. Its interpretation is exactly: **legacy pre-v18 / epistemic basis
unknown**. No value is backfilled.

The production capture does not prove that both non-null semantic values were
independently issued in production. The reported implementation commits and
three-way unit test are recorded separately as upstream reports because their
short commit IDs could not be resolved in the public repository inspected.

Validate the package with:

```text
python tools/validate_invinoveritas_epistemic_basis_v18.py
python -m unittest tests.test_invinoveritas_epistemic_basis_v18 -v
```

No offline `decision_ref` recomputation is claimed. This repository does not
pin an independent RFC 8785 implementation for the InvinoVeritas preimage, so
the evidence is scoped to exact public retrieval and `/verify-proof`
reproduction rather than an approximate canonicalizer.
