# trustless-ai · primitives registry

What's **already built** — so nobody re-explains or reinvents it. `primitives.json` is the **index**, verified 2026-09-03.

> **Index, not authority.** This registry only *points at* proofs; it is never itself the source of truth. Authority stays with the referenced **contract bytes** (`eth_getCode`), **repo state**, or **conformance package**. A mismatch means the *entry* is stale — not that the registry is truth. Run [`check.py`](check.py) (CI on every push) to recompute every entry against its authority and fail on drift. *(Rule sharpened by Pavlo in the WG.)*

Status: 🟢 **LIVE** (deployed/live) · 🟡 **SHIPPED** (code + vectors, verifiable) · 📄 **PUBLISHED** (note, CC0) · 🔵 **DRAFT** (spec, in the ERC process).

## 🟢 LIVE — on-chain (eth_getCode-verified)
- **AgentMarketEscrow** — On-chain escrow for agent services — list, buy, settle. · `0x82feaa28527adddfba29b5587c7b58d3e1e2c739` (mainnet)
- **MCPEntitlementRegistry** — Buy an MCP capability that's carried by the agent NFT. · `0x6374556D1c19924584644BD48ebecF444e43Ed9F` (mainnet)
- **TruthAnchor — ERC-8281 OCP (ours)** — Our ERC-8281 commitment anchor: record(digest)->Recorded; /verify showcase L3 reads it. Distinct from Vincent Wu's ERC-8263 TruthAnchorV1 (a separate primitive). · `0x1e2A118a2bf1C240aE6fDe187c07f905D360f094` (mainnet)
- **AttestationIndex — ERC-8281-compatible (ccip-router)** — ERC-8281 OCP-compatible commitment store (signerOf/commitmentOf) — the ccip-router mesh anchor. · `0xc7BCCD785Fb994e570d0ca10D0F7899d87C82210` (mainnet)
- **GenesisAgentRegistry (production)** — Mint-your-agent registry — the live deployment used by ai.verticecriativo.pt. · `0x8b5AF3A59f81c7e16617E8Eb824BC6FfB792A2C3` (mainnet)
- **GenesisAgentRegistry (reference)** — Second mainnet deployment, Sourcify-verified — the genesis-self-source example in agent-contracts-examples. · `0xe91934aB1f6A40cc1Bb4cD530FEFF56dFE524963` (mainnet)
- **PqBindingAnchor — wallet PQ binding** — Non-custodial WALLET PQ key binding, first-write-immutable — testnet rail, mainnet after testing. NOTE: the AGENT PQ binding is separate and LIVE — KYA-L4 (SLH-DSA + ML-DSA) attestor binding anchored on mainnet via TruthAnchor 0x1e2A118a (tx 0x469655a0…); 29 agents epoch-anchored on Base Sepolia; recompute at ai.verticecriativo.pt/quantum. · `0x0E6A09577f22A38239d4916C092E149BfB4AB57d` (sepolia)

## 🟢 LIVE — services
- **cross-reference-console** — multi-operator mutual-recompute surface — LIVE at trustless-ai.eth. · github.com/trustless-ai/cross-reference-console

## 🟢 LIVE — surfaces (hit them, recompute)
- **gateway.verticecriativo.pt/agent/verify** — Public no-auth attestation verify — hand it a hash, get the attested turn back. · https://gateway.verticecriativo.pt/agent/verify/0x096e9df2fccbaf49525a22d3537670ec83746157846f0c25509a6483fe1d0a91
- **ai.verticecriativo.pt/verify** — The /verify four-surface recompute showcase (WYRIWE L1-L3 + EIP-712 L4 + on-chain anchor). · https://ai.verticecriativo.pt/verify
- **ai.verticecriativo.pt/review** — invinoveritas /review verdict — recompute a signed review in-browser (NIP-01 + BIP-340). · https://ai.verticecriativo.pt/review
- **ai.verticecriativo.pt/quantum** — Post-quantum key-binding recompute (SLH-DSA / ML-DSA), served live. · https://ai.verticecriativo.pt/quantum
- **cross-reference-console (trustless-ai.eth)** — Multi-operator mutual-recompute matrix — LIVE on trustless-ai.eth. · https://trustless-ai.eth.limo/

## 🟡 SHIPPED — recompute primitives (26) · `recompute-kit/conformance/`
Each is a recomputable recipe with conformance vectors — run the suite to check any of them:
`pq-key-binding-v0`, `pq-key-binding-v1`, `pq-key-binding-v1-profile`, `pq-recovery-classes-v0`, `captured-admission-v0`, `captured-admission-v0-review-profile`, `captured-admission-v0-review-profile-deadline`, `companion-envelope-v0`, `convention-hash-v0`, `provenance-anchor-v0`, `storage-root-v0`, `encode-json-utf8-lf-v0`, `erc-8309-envelope-v0`, `erc8275-win-rate-bps-v0`, `communication-chain-v0`, `chronicle-checkpoint-continuity-v0`, `crc-claim-v0`, `aggregate-budget-v0`, `dex-calldata-v0`, `ens-write-v0`, `id-write-v0`, `nft-fulfill-v0`, `deils-leg2-reveal-v0`, `tee-inference-v0`, `tee-inference-enclave-v0`, `serializer-bindings`

## 🟡 SHIPPED — tools & components
- **verify-layer** — verify-don't-trust layer — prove account/storage state via eth_getProof vs stateRoot. · github.com/trustless-ai/verify-layer
- **recompute-kit** — the toolkit: recompute primitives + recipes + conformance vectors + MCP. · github.com/trustless-ai/recompute-kit
- **agent-sdk** — off-chain SDK — typed contract clients + deploy/test kit for the agent ERCs. · github.com/trustless-ai/agent-sdk
- **ccip-router** — the coordination layer CCIP-Read was missing — peer sync, dedup, mesh. · github.com/trustless-ai/ccip-router
- **zkIE** — Zero-Knowledge Inference Engine (prototype). · github.com/trustless-ai/zkIE
- **recompute-lens** — human surface over recompute-kit — watch an off-chain claim recompute. · github.com/trustless-ai/recompute-lens
- **eip7702-rescue** — forensic MCP + hardened delegate for atomic EIP-7702 asset rescue. · github.com/trustless-ai/eip7702-rescue
- **pq-agent-binding** — recomputable post-quantum key binding for on-chain AI agents. · github.com/trustless-ai/pq-agent-binding
- **agent-ercs** — ERCs + base implementations for the trustless-AI agent stack. · github.com/trustless-ai/agent-ercs

## 📄 PUBLISHED — notes (CC0)
- **collapsed-state-note** — 'A written rule has no failure mode' — collapsed states + the five tiers. · github.com/trustless-ai/collapsed-state-note
- **observation-conditions-note** — 'A reading is incomplete without the conditions that produced it.' · github.com/trustless-ai/observation-conditions-note
- **composed-attestation-note** — four independent commitments over one event — the seam rules. · github.com/trustless-ai/composed-attestation-note

## 🔵 DRAFT — ERCs (in the ERC process)
- **ERC-8299 — WYRIWE — what-you-run-is-what-you-explain (input provenance).** — co-author (TMerlini+Vincent+Fede+Jimmy+Damon). · ethereum/ERCs#1810
- **ERC-8354 — Confidential Agent Policy Verdicts (ZK allow/deny).** — co-maintainer; expiry-bound circuit PR ethereum/ERCs#1989. · ethereum/ERCs (merged #1919)
- **ERC-8373 — Post-Quantum Anchored Key Binding.** — author. · assets/erc-8373 (ethereum/ERCs)
- **ERC-8294 — VNI — Verifiable Network Inference.** — co-author (Tiago). · ethereum/ERCs

## Detect drift — `check.py`
Recomputes every entry against its authority and refuses to let one source silently decide:
- **contract** → `eth_getCode` on **≥2 distinct-provider RPCs**. They must *agree*: both see code → `PASS`, both empty → `STALE`. **Disagree** → `UNRESOLVED` (we don't pick a side). **<2 answer** → `CANNOT_CHECK` — a required check that can't run fails *closed*, never a silent pass. An RPC is a resolution *transport*, not chain-state *authority* (one public node once returned a false-empty for a live contract). *"Distinct provider" is by endpoint, not a formal independence criterion — providers may share upstreams, so agreement is corroboration bounded by that.* Corroboration is not re-derived consensus — full header verification (`eth_getProof` / light client) is the further leg the verify-layer carries.
- **repo / note** → the repository resolves (`gh api`); a transport error is `CANNOT_CHECK`, not a pass.
- **recompute-recipe** → the conformance package exists in `recompute-kit/conformance/`.
- **erc** → index-only here; verify at the ERC PR.
```
python3 check.py   # ✅ PASS ❌ STALE 🟠 UNRESOLVED 🚫 CANNOT_CHECK ⚠️ SKIP 📄 INDEX
                   # exit 1 = drift · exit 2 = unresolved/cannot-check (fail closed) · exit 0 = clean
```
Required checks (contract/repo/recipe) fail closed; `SKIP` is only for genuinely non-required cases. Works keyless (two public RPCs corroborate); set `ALCHEMY_KEY` / `RPC_URL_*` to add a trusted one.

---
55 entries. Authority > index, always. CC0.
