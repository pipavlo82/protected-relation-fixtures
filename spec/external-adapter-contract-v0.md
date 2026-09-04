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

## 3. Response

`adapters/v0/response-schema.json` defines the response. An evaluator returns
exactly one semantic outcome:

```text
PRESERVED | VIOLATED | UNVERIFIABLE
```

The response echoes the challenge digest, protected-relation profile digest,
and evaluator identity. It includes a reason code, optional reason detail, and
opaque evidence items. It contains no benchmark correctness label or mismatch
classification. A response content digest is recorded outside the response in
the execution transcript, avoiding self-reference.

Unknown outcomes, malformed JSON, empty output, nonzero exit, timeout, binding
mismatch, and evaluator exceptions are adapter/conformance failures. They are
not semantic preservation and are not silently converted to `UNVERIFIABLE`.
When an evaluator can execute but cannot justify a semantic conclusion, it must
return a well-formed `UNVERIFIABLE` response with an explicit reason.

## 4. Process protocol

The generic command protocol is:

```text
stdin:  one JSON request followed by LF
stdout: one JSON response
exit 0: response available for schema and binding validation
nonzero: adapter execution failure
```

`adapters/v0/run_adapter.py` accepts a command as an argument vector; it does not
invoke a shell or require a network. External adapters may use network or model
APIs, but scoring begins only after their response is captured and validated.

## 5. Transcript binding

Every command run produces a transcript containing the request digest, raw and
normalized response digests, evaluator identity, command vector, non-authority
timestamp, an exact base64 carrier and SHA-256 for raw stdout, a UTF-8 display
form, stderr, normalized response, process exit code, and a separate adapter
execution status.

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

## 7. Reference adapter

The deterministic reference adapter supports the six frozen challenge
identifiers and implements only their public, declared semantic rules. It reads
only a validated blind request. It does not read or import the oracle or scorer.
An unsupported challenge or protected relation profile returns `UNVERIFIABLE`
with an explicit reason; insufficient semantic input also fails closed.

## 8. Non-goals

This contract does not expose credentials, run a live model, alter frozen v0,
start v1, define external-domain truth, or claim deterministic semantic
reproduction for evaluators whose execution inputs are not closed.
