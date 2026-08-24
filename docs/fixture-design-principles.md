# Fixture Design Principles

## 1. Make the protected relation explicit

A fixture is only meaningful if it says what semantic relation is actually being protected. Without that, the same pair of objects can look either equivalent or non-equivalent under different informal interpretations.

## 2. Separate weak observation from protected semantics

Each fixture should distinguish:

- what a weak observer still sees as unchanged
- what the protected semantic relation has actually lost or changed

## 3. Prefer fail-closed expectations

The target failure mode is not raw difference detection. The target failure mode is false PASS under a preserved weak projection. Expected outputs should therefore be framed in fail-closed terms.

## 4. Include real-world as well as synthetic cases

The strongest fixture classes are not only elegant synthetic examples. They also arise from real version skew, vocabulary drift, multiplicity collapse, relation relabeling, and local-vs-global scope mistakes.

## 5. Avoid overclaiming from one preserved view

A preserved count, degree, shape, parseability, or endpoint output is not enough by itself. The fixture should force the evaluator to say whether the protected semantic object is still the same.
