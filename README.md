# Protected Relation Fixtures

Protected Relation Fixtures is a small benchmark corpus for cases where weak observational equality is preserved while the protected semantic relation is not. It is designed for fail-closed verifiers, provenance systems, and transformation-stability methods that must distinguish count/shape preservation from actual semantic preservation.

## Core normative claim

> Equality under a weak observation must not imply equivalence of the protected semantic relation.

Operational version:

> Do not trust a preserved projection; recompute the protected semantic object and compare that instead.

## What this repo contains

- a small starter set of canonical fixture cards
- compact framing docs for the benchmark lane
- a seed structure that can later grow into vectors, schemas, tests, or adapters

## Current starter fixtures

1. Local neighborhood preserved, global identity changed
2. Relation type changed, shape preserved
3. Version skew / unknown-member collapse
4. Multiplicity collapse
5. Pass, pass, compose, fail

## Scope

This repo is meant to stay separate from any single frozen TSEI authority-run lane or ReceiptOS run history. It is a reusable benchmark/methodology seed for false-equivalence cases where weak observers can overclaim semantic preservation.
