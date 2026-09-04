# PRF Applied to Trustless AI — Deterministic Protected-Relation Audit v0

## 1. Motivation

PRF was first exercised as a controlled semantic-discrimination benchmark against LLM evaluators. This study is different. It applies the same protected-relation methodology directly to real public system sources and live verification surfaces without using an LLM as the evaluator.

## 2. Method

Each case follows one explicit chain:

```text
raw / observed state
  -> weak observation
  -> protected relation and scope
  -> deterministic comparison
```

Equality of a value, hash, or byte string is evidence only for the relation it actually observes. It does not automatically preserve verification authority, provenance identity, security tier, exact as-of authority, or evidence completeness.

All upstream source statements are tied to exact Git commits and captured bytes. Live observations are read-only request/response captures and are time-scoped. Chat statements are context only and were not used as authority.

## 3. Source Authority

| Repository / surface | Exact commit or version | Captured paths | Live reproduction status |
|---|---|---:|---|
| `trustless-ai/recompute-kit` | `d21bcc718bf505b46c4d32d7f3c858dff9d3e8bc` | 5 | Source captured; storage-proof runtime not executed because local `cast` was unavailable |
| `trustless-ai/verify-layer` | `84afc4b738dc37269089c858404eed8086435f5d` | 1 | Source captured; runtime credential-gated |
| `trustless-ai/trustless-agent-substrate` | `a344ef80f7c52c03b9183814d1874b8054639c3e` on default `feature/tas-poc` | 9 | Source and tests captured |
| `trustless-ai/primitives` | `6b39e9540d4bd0a78decb588c0a8e328c303f208` | 3 | Source captured |
| `trustless-ai/ccip-router` | `6bd66611b88a4751a0acc233c718aa9a13294de4` | 4 | Source captured; public verify response reproduced |
| `trustless-ai/agent-contracts-examples` | `60855b200745d2f6dfd24b266f95ca92ce102ed2` | 2 | Source captured; Base Sepolia and Ethereum code reproduced |
| `trustless-ai/agent-ercs` | `01283ca57305f915afb560d23359a27fd748eb5a` | 8 | Source captured |
| Public verification gateway | observed 2026-09-04 | 3 request/header/response payloads | `LIVE_REPRODUCED` |
| Base Sepolia JSON-RPC | chain 84532, exact block `0x2c26737` for the attestation | 14 payloads | `LIVE_REPRODUCED` |
| Ethereum JSON-RPC | chain 1, captured block `0x18b42c0` | 6 payloads | Contract code reproduced; no same-digest mainnet event claimed |

`source-inventory.json` is normative for every captured path, upstream blob, byte length, and SHA-256. Counts in this table are explanatory.

## 4. Case Matrix

| Case | Weak observation | Protected relation | Expected | Source basis |
|---|---|---|---|---|
| TAI-001 | Same state value/root and valid MPT path | `verification_authority_class` | VIOLATED | recompute-storage-proof and verify-layer |
| TAI-002 | Same digest is anchored | `anchor_security_authority_class` | VIOLATED | chain-aware ERC-8281 contract plus live Base Sepolia and pinned mainnet code |
| TAI-003 | Same path/content bytes | `profile_authorized_repository_identity` | VIOLATED | TAS Profile and Repository resolution |
| TAI-004 | Same returned value | `as_of_chain_authority` | VIOLATED | TAS EIP-1898 exact block-hash reads |
| TAI-005 | Same human-readable claim/result | `claim_to_observation_binding` | VIOLATED | OCP/WYRIWE source, gateway result, and chain event |
| TAI-006 | Same committed inner bytes and declared outcome | `nested_semantic_recomputation_requirement` | UNVERIFIABLE | no general recursive rule in pinned sources |
| TAI-007 | Base64 line wrapping differs; decoded bytes are equal | `profile_authorized_repository_file_identity` | PRESERVED | TAS strict transport normalization |

## 5. Source-Backed Findings

### Semantic and authority distinctions

Six cases establish source-backed protected-relation distinctions. These cover header authority, anchor authority class, Profile-selected repository identity, exact as-of authority, claim-to-observation binding, and a transport normalization boundary.

### Narrow authority overclaim

`recompute-storage-proof` obtains the header through a supplied RPC and verifies MPT paths against that returned `stateRoot`. The captured source nevertheless describes the root as “canonical” and prints “no trusted RPC read.” That wording does not preserve the header-authority boundary and is recorded narrowly as `SOURCE_BACKED_AUTHORITY_OVERCLAIM`. It is not called an exploit or vulnerability.

### Positive fail-closed properties

- verify-layer labels the state proof `RE-DERIVED` and the header `RPC-TRUSTED`, and describes a light-client replacement seam.
- TAS repository resolution derives the canonical repository, exact commit, and path from the Profile snapshot; it exposes no caller repository override.
- TAS performs EIP-1898 block-hash reads with `requireCanonical: true`, rechecks the block hash, and does not silently fall back to a number-only read.
- TAS accepts LF/CRLF base64 wrapping only as transport normalization while retaining repository, commit, path, size, and decoded-byte checks.

### Repaired historical gaps

No prior gap is claimed repaired by the pinned sources. The count is zero.

### Deferred and unverifiable

No general current source rule was found for recursively upgrading committed inner receipt bytes to reproduced inner semantics. TAI-006 is therefore `DEFERRED_NO_CURRENT_SOURCE_SURFACE` with deterministic result `UNVERIFIABLE`.

## 6. Live Reproduction

The public gateway returned a verification object for digest `0x096e…0a91`. Direct Base Sepolia RPC reproduced chain id 84532, non-empty code for the documented TruthAnchor, the exact transaction, a successful receipt, the exact containing block hash, and a `Recorded` event binding that digest to the committer.

Direct Ethereum RPC reproduced chain id 1 and non-empty code for the documented mainnet TruthAnchor at block `0x18b42c0`. It did not establish a mainnet event for the case digest. No Bitcoin OTS proof was found or claimed.

The verify-layer runtime was not executed because its captured source expects a local Alchemy key; no hidden credential was used. The storage-proof runtime was not executed because the required local Foundry `cast` executable was unavailable. Neither limitation was converted into a positive result.

Exact endpoints, requests, responses, blocks, transaction hash, and limitations are recorded in `live-reproduction-summary.json` and inventoried byte-for-byte.

## 7. Detailed Cases

### TAI-001 — state proof versus header authority

The raw implementation fetches a block header from RPC, obtains its `stateRoot`, and re-derives account/storage MPT membership relative to that root. The weak observation sees equal values and a valid path. The protected relation also includes how the header was authenticated. `RPC_TRUSTED` and `CONSENSUS_RE_DERIVED` are not equivalent, so the relation is VIOLATED even if the root and value are the same.

### TAI-002 — anchor security authority class

The Base Sepolia commitment was reproduced. Current source documents chain-specific validity and a separate Ethereum mainnet anchor. “Digest is anchored” is too weak to erase chain identity, testnet/mainnet tier, and contract identity. The case is a source-supported same-digest counterfactual; it does not claim the digest was actually recorded on mainnet or Bitcoin.

### TAI-003 — Profile-authorized repository identity

TAS resolves repository identity, exact commit, and path from the Profile snapshot. Equal bytes returned from another repository preserve content equality but violate the Profile-authorized identity relation. Current TAS is fail-closed against caller substitution at this boundary.

### TAI-004 — exact as-of chain authority

An equal current or number-selected value does not preserve an exact hash-bound canonical read. Current TAS uses `blockHash` with `requireCanonical: true` and rejects weaker fallback. The weaker state is a counterfactual, not a claim about current TAS behavior.

### TAI-005 — claim versus observation binding

The source and live evidence distinguish a committed claim/observation digest from unbound text. The public chain event proves existence of the captured digest under the observed transaction and block. It does not by itself prove every off-chain tool action or semantic truth. `CLAIM_COMMITTED`, `OBSERVATION_BOUND`, and `SEMANTICALLY_VERIFIED` remain separate statuses.

### TAI-006 — nested receipt semantic transitivity

Committed inner receipt bytes, even if they contain a declared `VERIFIED` outcome, are not automatically a reproduced inner proposition. Because no general recursive outer-profile rule was found, the case remains UNVERIFIABLE rather than inventing nested semantics.

### TAI-007 — preservation control

The TAS GitHub client removes CR/LF line wrapping before strict canonical base64 decoding. If Profile-selected repository, commit, path, decoded size, and decoded bytes remain identical, only transport representation changes. The protected relation is therefore PRESERVED. This control prevents a trivial always-VIOLATED audit.

## 8. PRF Relation Axes

- Identity: TAI-003 protects Profile-authorized repository identity.
- Relation type: TAI-001 distinguishes MPT derivation from header authentication; TAI-005 distinguishes commitment from semantic verification.
- Scope: TAI-005 limits what observation fields and chain evidence establish; TAI-006 exposes unresolved dependency closure.
- Temporal/as-of authority: TAI-004 protects exact canonical block-hash selection.
- Security/anchor authority: TAI-002 protects chain and security tier.
- Representation normalization: TAI-007 is a positive preservation control.

No strong multiplicity or direction case was added because the pinned sources did not support one without padding the study.

## 9. What This Does NOT Prove

- A semantic or documentation mismatch is not automatically an exploitable security vulnerability.
- PRF does not claim universal external-domain truth.
- A public endpoint result is pinned to the observed version and time.
- A cryptographic commitment does not automatically establish semantic truth.
- Exact artifact identity does not automatically establish authority equivalence.
- No LLM or model judgment is used in this audit.

## 10. Relationship to Earlier LLM Experiments

Earlier PRF experiments tested whether LLM evaluators could correctly discriminate protected relations. This audit instead tests real-system relation boundaries themselves deterministically. The two evidence layers are complementary, and their denominators and results must not be mixed. Prior model judgments are not imported into these case outcomes.

## 11. Reproduction

```sh
python tools/build_trustless_ai_source_inventory.py
python tools/validate_trustless_ai_deterministic_case_study.py
python tools/validate_v0_freeze.py
python -m unittest tests.test_trustless_ai_deterministic_case_study -v
python -O -m unittest tests.test_trustless_ai_deterministic_case_study -v
python -m unittest discover -s tests -v
python -O -m unittest discover -s tests -v
```

The inventory builder rechecks upstream source blobs and regenerates only the inventory. Public RPC requests in `live/` are reproducible with any public endpoint for the named chain, subject to normal endpoint availability. Evaluator-side or model execution is neither needed nor permitted for this audit.

## 12. Next Work

- discuss source-backed findings with Trustless AI maintainers;
- optionally expose these real-system cases later as blind external-evaluator challenges;
- community review;
- possible standardized real-system PRF profiles;
- later ERC motivation.

No item above is performed by this audit.
