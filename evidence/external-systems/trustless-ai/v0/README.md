# Trustless AI deterministic PRF case study v0

This additive evidence lane applies the Protected Relation Fixtures method to pinned public Trustless AI sources and read-only public surfaces. It is not part of the frozen PRF v0 corpus and does not modify that release.

The audit separates raw state, weak observation, protected relation, and deterministic result. It uses no LLM or semantic model evaluator. The seven cases include one preservation control, five violated protected relations, and one fail-closed deferred case.

Authority is limited to exact captured upstream bytes, pinned Git identities, and captured public endpoint/RPC results. Chat context is not authority. Source-backed distinctions and wording problems are not automatically exploitable vulnerabilities.

Validate with:

```sh
python tools/validate_trustless_ai_deterministic_case_study.py
python tools/validate_v0_freeze.py
python -m unittest tests.test_trustless_ai_deterministic_case_study -v
```

The source inventory is a closed byte inventory for `sources/` and `live/`. `cases.json` declares the deterministic comparisons; `case-results.json` records their outcomes; `live-reproduction-summary.json` distinguishes reproduced, credential-gated, unavailable, and deferred checks.
