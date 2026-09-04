# External Adapter Contract v0

**Status:** additive post-v0 adapter contract candidate

**Identifier:** `external-adapter-contract-v0`

## 1. Boundary

This contract lets an external evaluator consume a blind Protected Relation
Fixtures challenge and return a semantic judgment. It is outside the frozen v0
authority surface and does not modify tag `v0`, `corpus/v0/`, `releases/v0/`,
the oracle, or any path in the v0 SHA-256 inventory.

The evaluator-facing path is oracle-blind. The benchmark supplies the protected
relation profile and evaluation input. The evaluator may apply that profile but
must not substitute or redefine it.

## 2. Request

`adapters/v0/request-schema.json` defines the request. It binds:

- contract schema and version;
- an opaque challenge identifier;
- SHA-256 of the exact stored blind-challenge bytes;
- the benchmark-supplied protected relation profile;
- SHA-256 of the profile's adapter-canonical JSON bytes;
- evaluator identifier, version, and configuration digest; and
- only the challenge's `before` and `after` evaluation input.

The adapter-canonical JSON form is UTF-8 JSON with lexicographically sorted
keys, no insignificant whitespace, literal non-ASCII scalar values, JSON string
escaping, and no non-finite numbers. The digest covers the resulting bytes
without a final LF. The current v0 profiles use only interoperable JSON values
and ASCII member names.

The fixture `class`, fixture metadata, projections, expected result, oracle
fields, scoring labels, and benchmark mismatch classifications are excluded.
The builder fails closed if answer-bearing fields are copied into a challenge or
request. Challenge identifiers must have the opaque form `prf-NNN` and must not
encode an answer class.

## 3. Evaluator output and bound response

The external evaluator has one responsibility: return the minimal semantic
payload defined by `adapters/v0/evaluator-output-schema.json`:

```json
{
  "outcome": "PRESERVED | VIOLATED | UNVERIFIABLE",
  "reason_detail": "human-readable semantic explanation"
}
```

These are the only evaluator-owned fields. The evaluator does not copy or
construct challenge, request, relation-profile, evaluator-identity,
configuration, transcript, invocation, or response digests. It does not return
a benchmark classification, oracle identity, adapter status, or normative
reason code.

`adapters/v0/response-schema.json` defines the full benchmark-bound response.
After validating the minimal payload, the deterministic wrapper constructs that
envelope. It copies the challenge and evaluator identity from the validated
request, computes the request, evaluator-output, and invocation digests, binds
the invocation to that exact request digest, sets `adapter_status` to
`RESPONSE_VALID`, and derives the reason code `EVALUATOR_JUDGMENT`. It preserves
the evaluator's outcome and explanation exactly and adds no invented semantic
evidence.

The permitted semantic outcomes are:

```text
PRESERVED | VIOLATED | UNVERIFIABLE
```

The model never echoes the protected-relation digest, but relation substitution
remains impossible through the contract: the benchmark supplies and validates
the profile and the wrapper copies its digest from the same request into the
response. The response content digest is recorded outside the response in the
execution transcript, avoiding self-reference.

Unknown outcomes, undeclared evaluator-output members, non-string explanation,
malformed JSON, empty output, nonzero exit, timeout, binding mismatch, and
evaluator exceptions are adapter/conformance failures. They are not semantic
preservation and are not silently converted to `UNVERIFIABLE`. A well-formed
minimal payload whose outcome is `UNVERIFIABLE` is instead a valid semantic
judgment and reaches the scorer unchanged.

## 4. Process protocol

The generic command protocol is:

```text
stdin:  one JSON request followed by LF
stdout: one minimal evaluator semantic payload
exit 0: evaluator output available for schema validation and deterministic wrapping
nonzero: adapter execution failure
```

`adapters/v0/run_adapter.py` accepts a command as an argument vector; it does not
invoke a shell or require a network. The runner captures raw stdout before
validating the minimal payload, creates the bound response through the common
wrapper, validates it, and records both forms in the transcript. External
adapters may use network or model APIs, but scoring begins only after output is
captured and validated.

## 5. Transcript binding

Every command run produces a transcript containing the request digest, exact
validated evaluator output and digest where available, invocation context and
digest, raw and normalized response digests, evaluator identity, command
vector, non-authority timestamp, an exact base64 carrier and SHA-256 for raw
stdout, a UTF-8 display form, stderr, normalized response, process exit code,
and a separate adapter execution status.

The wrapper-owned invocation context includes the exact request digest. A
captured evaluator output cannot be bound to another request using its original
invocation context; that attempt fails explicitly as replay. This is request
binding, not a claim that a nondeterministic evaluator will repeat its judgment.

A transcript binds what was returned under a declared evaluator identity and
configuration. It does not automatically prove that an LLM or other
nondeterministic evaluator would return the same semantic judgment again.

## 6. Benchmark-side scoring

Only `adapters/v0/score_results.py` reads the frozen oracle. The evaluator,
request builder, validator, command runner, and reference adapter do not score.
The scorer keeps three dimensions separate:

1. evaluator semantic outcome;
2. adapter execution status; and
3. benchmark mismatch classification.

The mismatch taxonomy is:

- `MATCH`;
- `UNSAFE_FALSE_PRESERVATION`;
- `UNSAFE_UNVERIFIABLE_UPGRADE`;
- `FALSE_VIOLATION`;
- `PRESERVATION_NOT_ESTABLISHED`;
- `VIOLATION_NOT_ESTABLISHED`; and
- `UNVERIFIABLE_MISCLASSIFIED_AS_VIOLATION`.

Adapter failures are counted separately and receive no semantic classification.
The scorer refuses an oracle, manifest, or v0 inventory whose exact SHA-256 is
not the frozen v0 identity. It also reconstructs the frozen challenge binding:
the request digest, profile, and evaluation input must match the exact challenge
bytes named by the pinned inventory. A request cannot preserve a frozen digest
while substituting different semantic input.

## 7. Reference evaluator

The deterministic reference evaluator supports the six frozen challenge
identifiers and implements only their public, declared semantic rules. It reads
only a validated blind request and emits the same two-field minimal semantic
payload required from every external evaluator. The common wrapper, not the
reference evaluator, constructs its full response envelope. It does not read or
import the oracle or scorer. An unsupported challenge or protected relation
profile returns `UNVERIFIABLE` with an explicit explanation; insufficient
semantic input also fails closed.

## 8. Non-goals

This contract does not expose credentials, run a live model, alter frozen v0,
start v1, define external-domain truth, or claim deterministic semantic
reproduction for evaluators whose execution inputs are not closed.
