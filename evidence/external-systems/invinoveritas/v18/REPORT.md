# PRF Applied to InvinoVeritas v18 — Epistemic-Basis Commitment Closure

## 1. Protected relation

Layer 1 is the semantic distinction:

```text
reject/evidence_against != reject/insufficient_evidence
```

The weak projection `verdict == "reject"` erases that distinction while
retaining the existing fail-closed action result.

Layer 2 is the recursive commitment distinction:

```text
epistemic distinction visible in response
!=
epistemic distinction cryptographically committed
```

The current v18 production proof closes Layer 2 by listing
`epistemic_basis` in the authenticated `decision_ref` preimage contract.

The historical implementation arc is recorded with an explicit authority
split. Upstream reports that `epistemic_basis` first exposed the Layer 1
distinction in the response while remaining outside `decision_ref`, which
recreated the same collapse at Layer 2, and that v18 added it to the preimage.
The unresolved implementation commits are not treated as public-source facts.
What is independently reproduced here is the final v18 production behavior,
its one-field tamper response, and the v17 compatibility behavior.

## 2. Independently reproduced production evidence

The exact event
`725eaec0331a0f08f5311fef3c6f85c5d7f080eec87bf12098682ab9bb924c87`
was retrieved from the public verdict-proof endpoint. It reports policy
`invinoveritas.review.v18`, verdict `reject`, `epistemic_basis: null`, and
decision reference
`sha256:55d9f7032dd271c495a0187d866ca45a9edd78d78a55b77cbd7405442bbc520d`.
Its stored field list contains `epistemic_basis`; its rule says every listed
field is present in the hashed preimage and absent optional values are JSON
`null`, never omitted.

The public verifier returned, for the unmodified event:

- `valid = true`
- `id_integrity = true`
- `signature_valid = true`
- `decision_ref_recomputes = true`

The tamper request changes only the event content's `epistemic_basis` value
from `null` to `evidence_against`. It preserves the stored verdict, decision
reference, event ID, signature, public key, timestamp, kind, and tags. The
public verifier returned:

- `valid = false`
- `id_integrity = false`
- `signature_valid = false`
- `decision_ref_recomputes = false`

The PRF result is specifically the last check: the protected semantic field is
inside the inner authenticated decision relation. The outer Nostr integrity
failures are expected consequences, but are not substituted for that proof.
The reviewer verdict remains `reject`; this is a commitment violation, not a
different verdict.

## 3. Legacy compatibility control

Public ledger entry 260 contains a v17 proof. Its stored
`decision_ref_preimage_fields` does not include `epistemic_basis`, and its
content has no such key. The public verifier returned `valid`, `id_integrity`,
`signature_valid`, and `decision_ref_recomputes` all true.

This is classified as `LEGACY_COMPATIBILITY_CONTROL`, not a failed v18 case.
Its only permitted epistemic interpretation is **legacy pre-v18 / epistemic
basis unknown**. Absence is not `evidence_against` and is not
`insufficient_evidence`.

## 4. Upstream-reported implementation facts

The binding commit `56e5999d` and preview/docstring follow-up `0a40e39f`
were reported upstream. Neither short ID resolved against the public
`babyblueviper1/invinoveritas` repository at pinned commit
`3bdea4f08d7a399acd07c4e6d36e34dd38fadee8`. The reported three-way
`test_different_epistemic_basis_produces_different_decision_ref`, per-proof
stored-preimage verification, and unchanged fail-closed action projection are
therefore labeled `UPSTREAM_REPORTED_NOT_PUBLICLY_RESOLVED`. They are not used
as independently reproduced repository facts. A global public GitHub commit
prefix search found no result for `56e5999d`; the two results sharing prefix
`0a40e39f` were unrelated repositories, not InvinoVeritas provenance.

## 5. Evidence and reproduction boundary

The raw public responses, exact requests, local one-field mutation, and current
public v17 source example are hash-inventoried. Reproduction uses:

```text
GET  https://api.babyblueviper.com/verdict-proofs/725eaec0331a0f08f5311fef3c6f85c5d7f080eec87bf12098682ab9bb924c87
POST https://api.babyblueviper.com/verify-proof
GET  https://api.babyblueviper.com/ledger/260
POST https://api.babyblueviper.com/verify-proof
```

Live results are observations at the recorded non-authoritative capture time.
The package does not claim independent observation of both non-null semantic
values in production, does not infer historical values, and does not call the
pre-v18 commitment gap an exploit or vulnerability. It records a real-world
protected-relation commitment-surface failure and its v18 closure.

An independent offline `decision_ref` recomputation is not claimed because the
PRF repository does not pin a suitable RFC 8785 implementation for this
external preimage contract. The public verifier result is preserved exactly;
no approximate JSON canonicalization is treated as equivalent.
