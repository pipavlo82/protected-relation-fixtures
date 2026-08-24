# Visual Formulations

These compact formulations are meant to give the repository a clear visual core.
They are not substitutes for the full protected-relation contract, but they make
the benchmark's direction immediately legible.

## 1. Core negative class

```text
P(S0) = P(S1)
while
S0 !=protected S1
```

Meaning:

- a weak projection remains preserved;
- the protected semantic relation does not.

This is the primary false-equivalence danger class.

## 2. Core mirror-positive class

```text
Raw(S0) != Raw(S1)
while
S0 =protected S1
```

Meaning:

- raw or representation-level drift exists;
- protected semantics are still preserved.

This prevents the benchmark from collapsing into a trivial "any diff => fail"
oracle.

## 3. Operational rule

```text
preserved projection
!=
preserved protected semantics
```

Expanded form:

```text
Do not trust a preserved projection;
recompute the protected semantic object and compare that instead.
```

## 4. Unknown-state protection

```text
UNVERIFIABLE(reason = X)
```

must not silently become:

```text
PRESERVED
```

merely because downstream vocabulary can no longer express `reason = X`.

Compact form:

```text
unknown != ok
```

## 5. Composition warning

```text
pass + pass != composition-safe
```

Local admissibility is not the same thing as global semantic preservation after
composition.

## 6. Repository-level intent

The role of this repository is to turn these formulations into:

- fixture cards,
- machine-readable vectors,
- oracle expectations,
- and eventually reusable benchmark adapters.
