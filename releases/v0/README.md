# Protected Relation Fixtures v0 Freeze Closure

This directory records the proposed exact-byte closure of Protected Relation
Fixtures v0. The freeze binds the already-reviewed benchmark surface; it does
not redesign fixture semantics or introduce an external evaluator.

## Identity model

`freeze-record.json` binds the exact pre-freeze source commit and tree. The Git
commit that first introduces this directory is derived from repository history
and must have that source commit as its direct parent. A future commit identifier
is never guessed or embedded in its own contents.

`sha256-inventory.json` independently binds each declared frozen artifact by
POSIX path, byte length, SHA-256, and role. It intentionally excludes itself and
`freeze-record.json` to avoid a digest cycle. Those two release records, along
with the inventory payload, are bound by the introducing Git commit.

The freeze validator derives that introduction commit from Git history, requires
it to have the exact source commit as its sole direct parent, and compares every
current frozen byte—including the record and inventory—with the corresponding
introduction-commit blob. A coherent later repin therefore cannot rewrite v0.

The Git commit and tree bind repository history and content under Git object
semantics. The SHA-256 inventory separately binds exact stored artifact bytes.
Neither mechanism manufactures semantic truth.

## Validation environment

`environment.json` records the canonical CI configuration and the environment
used for the local freeze-closure run. This is an environment record, not a
claim of bit-for-bit runtime determinism. In particular, the GitHub-hosted
runner label and major-version action tags are not content-addressed runtime
images.

Run the closure gate with:

```text
python tools/validate_v0_freeze.py
```

## Authority boundary

The freeze establishes:

> Exact benchmark artifacts, declared semantic contracts, validation machinery,
> discrimination witnesses, and second-implementation reproduction evidence are
> bound to an immutable repository state and exact-byte inventory.

The second-review claim remains:

> Two separately implemented evaluators reproduce the declared
> relation-discrimination contract over the exact synthetic witness suite.

The remaining boundary remains:

> The synthetic witness construction, alias maps, scope declarations, and
> completeness markers remain declared benchmark inputs. Agreement between two
> implementations does not independently establish that those declarations
> correctly model every external domain.

The freeze does not establish objective semantic truth for every external
domain, correctness of every real-world alias map or future scope declaration,
universal equivalence semantics, or correctness of external evaluators not
covered by this release.

## Versioning

Once this candidate is independently audited and merged, frozen v0 artifacts
must not be rewritten in place. Semantic changes require a successor version or
lane. Corrections to freeze metadata that do not alter frozen semantic bytes
must be append-only and explicitly classified. Future fixtures must not be
silently added to the frozen v0 universe.
