# Guarantee-preservation v0

This is an **experimental bounded conformance profile** for a declared guarantee-transfer obligation. It compares what an identified domain adapter actually establishes with what a separate consumer claims from that result. The contribution is an executable cross-layer check with native results retained, not a new ERC, accepted standard, or universal semantic-verification method. This additive profile is outside the frozen `corpus/v0` contract.

## Contract and consumer boundary

A common contract identifies the target and context, the protected relation, required evidence, adapter and profile versions, native result, carried guarantees and explicit omissions. The consumer selects its own policy and separately accepts the basis for applying it. Dependencies, source pins and digests can bind declared inputs; they do not prove that the dependency set is complete or that the procedure is sound for a wider proposition. A consumer must not manufacture those premises from a successful dependency check.

The transfer verdict uses PRF's [three-outcome model](../../spec/outcome-model.md). Malformed, unsupported or conflicting evidence, failed bindings and unavailable accepted premises yield `UNVERIFIABLE`. Any required `UNKNOWN` also yields `UNVERIFIABLE`; otherwise a required `FALSE` yields `VIOLATED`, and all required relations `TRUE` yield `PRESERVED`. A demonstrated prohibited grade promotion can therefore violate its grading obligation without judging scan truth. Each adapter's full native result remains separately available. A native negative result can be correctly reproduced; a scalar success, level, digest or `reproduced: true` cannot replace that result or its scope.

The adapter does not select the consumer's policy. Agreement about the policy and evidence basis is an explicit condition of this bounded contract; it is not a proof of the policy's completeness, correctness or suitability. `PRESERVED` protects only the declared obligation under those premises. The consumer API is `consume(envelope, policy=..., accepted_basis=..., registry=...)`; these three caller-supplied arguments form its trust boundary. The function does not establish who accepted them. Producer flags, references and hashes confer no authority. Decisions export the exact selected context and policy digest, observed adapter/evaluator/context/basis, and envelope/evidence digests for audit; these bindings do not establish acceptance authority.

## Identified domains

| Domain | Adapter ID | Evaluator ID |
| --- | --- | --- |
| PRF | `prf-award-actual-settlement-adapter-v0` | `prf-supplied-tuple-evaluator-v0` |
| recompute-kit | `kit59-authentication-grade-adapter-v0` | `kit59-pinned-contract-evaluator-v0` |

Adapter semantics live in [guarantee_preservation_adapters.py](../../tools/guarantee_preservation_adapters.py); the [neutral consumer](../../tools/guarantee_preservation.py) has no case-name branches. The context subject digest binds both the input and native output. The PRF domain is pinned to base `fac26d2e8346aeab08194343b78c345d235c6935`; [sources.json](sources.json) records the upstream source hashes and execution limits.

### PRF award-to-actual-settlement

The local [award profile](../award-actual-settlement-v0/README.md) recomputes a synthetic finalized-award-to-observed-completion tuple: target reference, tender, winning fulfiller, accepted work, one observed completion and actual payment equal to award price. Its native outcome and reason are retained. The adapter carries that tuple-level result and its bounded assumptions; it carries no universal truthfulness guarantee, authenticated chain provenance, task-version authority, or replay-prevention guarantee.

In particular, fixed reward 100 can retain the weak winner/accepted/completion projection of award price 50 while violating the payment obligation. A matching tuple establishes the scoped relation, not the truth of every economic claim downstream.

### recompute-kit scan-subject-binding

The second domain is `trustless-ai/recompute-kit`'s `scan-subject-binding-v0`, pinned at `a725f2e6aa0d887b8bd51d9081c07dbcad5c9c87`. Its [native checker](https://github.com/trustless-ai/recompute-kit/blob/a725f2e6aa0d887b8bd51d9081c07dbcad5c9c87/conformance/scan-subject-binding-v0/scan_check.py#L101-L169) distinguishes `replay_bindings`, `result_only_check`, `subject_bound_check`, `evidence_grade` and `replay_failures`. These fields must remain inspectable without replacing them with a generic success boolean.

This profile uses pinned upstream inputs and **source-derived expectation outputs**. Those outputs are fixtures derived from the reviewed checker and vectors; they are not captured upstream stdout. The upstream checker is not executed by this profile. Local adapter/consumer execution therefore makes no claim of an upstream run or independent kit implementation.

For [c6](https://github.com/trustless-ai/recompute-kit/blob/a725f2e6aa0d887b8bd51d9081c07dbcad5c9c87/conformance/scan-subject-binding-v0/vectors.json#L802-L808), the expected native result is:

```json
{
  "replay_bindings": "FAIL",
  "result_only_check": "VALID",
  "subject_bound_check": "CANNOT_ESTABLISH",
  "evidence_grade": null,
  "replay_failures": ["signature"]
}
```

`CANNOT_ESTABLISH` with a null grade maps to `UNVERIFIABLE` for the transfer obligation, even if a case-level reproduction expectation succeeds. Within the separately accepted source-expectation model, an [M9-style mutation](https://github.com/trustless-ai/recompute-kit/blob/a725f2e6aa0d887b8bd51d9081c07dbcad5c9c87/conformance/scan-subject-binding-v0/mutation_check.py#L25-L33) that promotes this invalid-signature result to `NO_FINDING`/`AUTHENTICATED_REPORT` yields `VIOLATED` for the grading obligation. It does not establish that the scan's factual finding is false. M8's missing replay-signature guard is a separate mutation. Native-integrity mismatches remain `UNVERIFIABLE`; the consumer does not loosen the contract to accept them. Unsupported bindings or versions alone do not establish an adapter bug.

Only the exact declared M8/M9 native controls in [kit59-fixtures.json](kit59-fixtures.json) are admitted; their observation/context bindings differ from baseline. Unsupported mutations yield `UNVERIFIABLE` rather than masquerading as pinned native bytes.

Upstream binding is bounded to k=1 and the effective dataset or recordwise corpus root. `AUTHENTICATED_REPORT` authenticates a manifest claim under the public test key; it does not establish scanner-origin execution or operational authorization. Native stdout does not supply an authority identity, subject digest, freshness/revocation status or version authority. These omissions cannot be filled from `case_id`.

## Prior art and scope

Related work already addresses profiles, policy-dependent interpretation and composite evidence. [RVR/ERC-8404's pinned draft](https://github.com/pipavlo82/ERCs/blob/7a9e63a80bce04db53c6550103c1d41eca35f3d1/ERCS/erc-8404.md#L185) separates profile-defined verification outcomes from independent recomputation status and bounds `REPRODUCED` to the defined procedure. [KYA/ERC-8419's pinned draft](https://github.com/garyyang-finchip/ERCs/blob/b8690e4162b2401c58e77935d057b6c85524a088/ERCS/erc-8419.md#L409) uses scheme-scoped conclusions and describes a lossy bridge; registry-local `resolveLocal` does not imply complete policy satisfaction. Both are drafts.

[SCITT architecture, RFC 9943](https://www.rfc-editor.org/rfc/rfc9943.html), a Proposed Standard, supports registration policies, optional domain payload checks and relying-party policies; registration alone does not establish statement truth. [COSE Receipts, RFC 9942](https://www.rfc-editor.org/rfc/rfc9942.html) protect specified verifiable-data-structure properties. The [composite-evidence verification draft](https://datatracker.ietf.org/doc/html/draft-nobuo-scitt-composite-evidence-verification-00) already proposes named profiles, relationship checks and structured incomplete/conflicting results. The [protected-object-binding draft](https://datatracker.ietf.org/doc/html/draft-nobuo-scitt-protected-object-binding-00) includes graph relationships and requires separate relation-assertion authorization. These two individual Internet-Drafts have no IETF endorsement. This profile claims neither full ERC/SCITT conformance nor general cross-domain equivalence.

## Reproduction and outside collaborator handoff

The [v0 contract schema](contract.schema.json) uses version `guarantee-preservation-v0` and stored-byte SHA-256 `44229b0a8322b4fe2f2c2946e0fa705e64c9bee4565693276e7db53155c5ae31`. Binding digests are `sha256:` plus lowercase SHA-256 of UTF-8 JSON serialized with sorted keys, compact separators, non-ASCII characters retained and nonfinite numbers disallowed. They bind the declared basis and dependency list, not their completeness or soundness. The [source lock](source-lock.json) records local artifact identities only.

Run from the PRF repository root:

```text
python -B tools/validate_guarantee_preservation.py
python -B -m unittest discover -s tests -p test_guarantee_preservation.py -v
python -B -O -m unittest discover -s tests -p test_guarantee_preservation.py -v
python -B -m unittest discover -s tests -p test_guarantee_preservation_mutations.py -v
python -B -O -m unittest discover -s tests -p test_guarantee_preservation_mutations.py -v
python -B tools/guarantee_preservation_mutations.py
```

The local suite recomputes PRF outputs and exercises source-derived kit expectations: 11 cases, with 4 `PRESERVED`, 5 `VIOLATED` and 2 `UNVERIFIABLE`. A matching suite exits 0 even though individual fixtures expect withheld or violated guarantees. Mutation kills require an applied source change, an adverse semantic mismatch and a preserved positive control; compilation failures, crashes, invalid output and damaged positive controls are not kills.

For a supplied contract envelope, choose the consumer policy explicitly:

```text
python -B tools/validate_guarantee_preservation.py --envelope FILE --policy-id policy-prf-price_preserving
```

The policy/basis configuration is [consumer-inputs.json](consumer-inputs.json), selected independently of the producer envelope. For this comparison mode, `PRESERVED` exits 0; `VIOLATED`, `UNVERIFIABLE` or input failure exits 2.

An outside collaborator needs this schema/digest, [suite](suite.json), source pins, unchanged fixture inputs, adapter IDs, selected consumer policy and separately accepted basis. In an independently authorized kit checkout at `a725f2e6aa0d887b8bd51d9081c07dbcad5c9c87`, produce a native JSON capture with the upstream checker. From that checkout's `conformance/scan-subject-binding-v0` directory, the [pinned upstream command](https://github.com/trustless-ai/recompute-kit/blob/a725f2e6aa0d887b8bd51d9081c07dbcad5c9c87/conformance/scan-subject-binding-v0/scan_check.py#L161-L173) can be captured as follows (POSIX shell example):

```text
python3 scan_check.py vectors.json > /absolute/path/scan.native.json 2> /absolute/path/scan.stderr.txt
```

Require upstream exit 0 and retain stderr separately. Import stdout untouched, without reformatting or filtering. This PRF code never invokes that checker.

Keep `scan.native.json` untouched. Keep the upstream `vectors.json` bytes matching SHA-256 `f9a1b3e547a55caf498f14ced1e239171f843fb9c81aa6e279fd6fd3f7446e89`. From the PRF root, compare the independently obtained capture:

```text
python -B tools/validate_guarantee_preservation.py --kit-vectors PATH/TO/KIT/conformance/scan-subject-binding-v0/vectors.json --kit-native-output PATH/TO/scan.native.json --policy-id policy-kit-c2
```

The selected supported policy may be `policy-kit-c2`, `policy-kit-c4`, `policy-kit-c4b` or `policy-kit-c6`. Matching c2/c4/c4b outputs yield `PRESERVED` and exit 0 for the scoped transfer obligation; c4b's native `CONTRADICTED` remains unchanged. Matching c6 yields `UNVERIFIABLE` and exit 2. The report retains the full parsed `native_capture`, native-file SHA-256 and complete selected native row. Vectors and native files are each read once; parsing and raw hashes use the same byte snapshot. The original file is still needed to preserve raw bytes; the comparison establishes neither its execution nor origin.

Retain stdout/stderr and exit codes. Report mismatches with case/policy ID, tested revision, schema/input/native hashes, expected and observed native fields, transfer verdict and accepted basis. Unsupported evidence must remain reported as unsupported. Preserve each file's evidence-class label: a source-derived expectation is not a runtime capture. No outside run or independently accepted consumer contract is claimed here. Selected upstream JSON data is CC0-1.0; [its notice](UPSTREAM-DATA-LICENSE.txt) is retained.
