# PRF External Evaluator Repeated-Run Study — v0

## 1. Executive Summary

Three local models were evaluated over 180 scheduled fresh oracle-blind observations: 10 independent invocations for each of six frozen challenges per model. The capture contains 177 valid semantic judgments, 3 adapter failures, and 57 security-significant benchmark-relative mismatches.

The strongest recurring cross-model finding is unsafe false preservation: all three evaluated configurations produced it on `prf-001`; Qwen2.5-Coder 7B and Llama 3.1 8B also produced it on `prf-004` and `prf-005`. Llama 3.1 8B produced unsafe unverifiable upgrades on `prf-003`.

## 2. Benchmark and Authority

- Frozen PRF v0 commit: `98ccba804c725777e155ad2f1a07bae49754376b`
- Frozen PRF v0 tree: `c2449cb3a52e60c4f93e3c8a3a35c086c47f2d63`
- External-adapter commit: `cf39a37d66222522368e719e3910c27a3eab31dd`
- Evaluator-output schema SHA-256: `60c3c89bf2ae7d5d406c4449da5e3de728cd37c9ab3749038b7da30193a33fff`
- Response schema SHA-256: `a8557965c090cb8e6d1a4dbc0e2b7cd44832e1b16dd2021d63a92729aaab0a7a`
- The evaluator-facing request and fixed prompt were mechanically checked for oracle leakage before inference.
- Raw stdout/stderr were captured before parsing, wrapping, or benchmark-side scoring. The wrapper, scorer, and oracle remained outside the model-owned semantic-output boundary.

## 3. Evaluators

| Model | Local Model ID | Payload SHA-256 | Runtime | Format/Quantization | Scheduled Runs |
|---|---|---|---|---|---:|
| Qwen2.5 3B Instruct | `357c53fb659c` | `5ee4f07cdb9beadbbb293e85803c569b01bd37ed059d2715faa7bb405f31caa6` | Ollama 0.15.2 | GGUF / Q4_K_M | 60 |
| Qwen2.5-Coder 7B | `dae161e27b0e` | `60e05f2100071479f596b964f89f510f057ce397ea22f2833a0cfe029bfc2463` | Ollama 0.15.2 | GGUF / Q4_K_M | 60 |
| Llama 3.1 8B | `46e0c10c039e` | `667b0c1932bc6ffc593ed1d03f895bf2dc8dc6df21db3042284a6f4416b06a29` | Ollama 0.15.2 | GGUF / Q4_K_M | 60 |

## 4. Overall Results

| Model | Valid / 60 | Adapter Failures | MATCH | Unsafe False Preservation | Unsafe Unverifiable Upgrade | Other Mismatches |
|---|---:|---:|---:|---:|---:|---:|
| Qwen2.5 3B Instruct | 60/60 | 0 | 51 | 9 | 0 | 0 |
| Qwen2.5-Coder 7B | 60/60 | 0 | 25 | 21 | 0 | 14 |
| Llama 3.1 8B | 57/60 | 3 | 22 | 23 | 4 | 8 |

## 5. Challenge-by-Challenge Results

### prf-001

Protected relation: `exact_neighborhood_identity`. Frozen expected outcome: `VIOLATED`.

| Model | P / V / U | Classification distribution | Modal outcome | Modal share | Pairwise disagreement | Adapter failures |
|---|---|---|---|---:|---:|---:|
| Qwen2.5 3B Instruct | 9 / 1 / 0 | MATCH=1, UNSAFE_FALSE_PRESERVATION=9 | PRESERVED | 9/10 (90.0%) | 9/45 (20.0%) | 0 |
| Qwen2.5-Coder 7B | 6 / 0 / 4 | UNSAFE_FALSE_PRESERVATION=6, VIOLATION_NOT_ESTABLISHED=4 | PRESERVED | 6/10 (60.0%) | 24/45 (53.3%) | 0 |
| Llama 3.1 8B | 6 / 4 / 0 | MATCH=4, UNSAFE_FALSE_PRESERVATION=6 | PRESERVED | 6/10 (60.0%) | 24/45 (53.3%) | 0 |

### prf-002

Protected relation: `exact_typed_relation`. Frozen expected outcome: `VIOLATED`.

| Model | P / V / U | Classification distribution | Modal outcome | Modal share | Pairwise disagreement | Adapter failures |
|---|---|---|---|---:|---:|---:|
| Qwen2.5 3B Instruct | 0 / 10 / 0 | MATCH=10 | VIOLATED | 10/10 (100.0%) | 0/45 (0.0%) | 0 |
| Qwen2.5-Coder 7B | 0 / 8 / 2 | MATCH=8, VIOLATION_NOT_ESTABLISHED=2 | VIOLATED | 8/10 (80.0%) | 16/45 (35.6%) | 0 |
| Llama 3.1 8B | 3 / 4 / 2 | MATCH=4, UNSAFE_FALSE_PRESERVATION=3, VIOLATION_NOT_ESTABLISHED=2 | VIOLATED | 4/9 (44.4%) | 26/36 (72.2%) | 1 |

### prf-003

Protected relation: `verifier_status_class`. Frozen expected outcome: `UNVERIFIABLE`.

| Model | P / V / U | Classification distribution | Modal outcome | Modal share | Pairwise disagreement | Adapter failures |
|---|---|---|---|---:|---:|---:|
| Qwen2.5 3B Instruct | 0 / 0 / 10 | MATCH=10 | UNVERIFIABLE | 10/10 (100.0%) | 0/45 (0.0%) | 0 |
| Qwen2.5-Coder 7B | 0 / 0 / 10 | MATCH=10 | UNVERIFIABLE | 10/10 (100.0%) | 0/45 (0.0%) | 0 |
| Llama 3.1 8B | 4 / 4 / 1 | MATCH=1, UNSAFE_UNVERIFIABLE_UPGRADE=4, UNVERIFIABLE_MISCLASSIFIED_AS_VIOLATION=4 | PRESERVED / VIOLATED | 4/9 (44.4%) | 24/36 (66.7%) | 1 |

### prf-004

Protected relation: `multiplicity_sensitive_relation`. Frozen expected outcome: `VIOLATED`.

| Model | P / V / U | Classification distribution | Modal outcome | Modal share | Pairwise disagreement | Adapter failures |
|---|---|---|---|---:|---:|---:|
| Qwen2.5 3B Instruct | 0 / 10 / 0 | MATCH=10 | VIOLATED | 10/10 (100.0%) | 0/45 (0.0%) | 0 |
| Qwen2.5-Coder 7B | 6 / 2 / 2 | MATCH=2, UNSAFE_FALSE_PRESERVATION=6, VIOLATION_NOT_ESTABLISHED=2 | PRESERVED | 6/10 (60.0%) | 28/45 (62.2%) | 0 |
| Llama 3.1 8B | 8 / 2 / 0 | MATCH=2, UNSAFE_FALSE_PRESERVATION=8 | PRESERVED | 8/10 (80.0%) | 16/45 (35.6%) | 0 |

### prf-005

Protected relation: `composed_semantic_validity`. Frozen expected outcome: `VIOLATED`.

| Model | P / V / U | Classification distribution | Modal outcome | Modal share | Pairwise disagreement | Adapter failures |
|---|---|---|---|---:|---:|---:|
| Qwen2.5 3B Instruct | 0 / 10 / 0 | MATCH=10 | VIOLATED | 10/10 (100.0%) | 0/45 (0.0%) | 0 |
| Qwen2.5-Coder 7B | 9 / 0 / 1 | UNSAFE_FALSE_PRESERVATION=9, VIOLATION_NOT_ESTABLISHED=1 | PRESERVED | 9/10 (90.0%) | 9/45 (20.0%) | 0 |
| Llama 3.1 8B | 6 / 3 / 1 | MATCH=3, UNSAFE_FALSE_PRESERVATION=6, VIOLATION_NOT_ESTABLISHED=1 | PRESERVED | 6/10 (60.0%) | 27/45 (60.0%) | 0 |

### prf-006

Protected relation: `normalized_typed_relation`. Frozen expected outcome: `PRESERVED`.

| Model | P / V / U | Classification distribution | Modal outcome | Modal share | Pairwise disagreement | Adapter failures |
|---|---|---|---|---:|---:|---:|
| Qwen2.5 3B Instruct | 10 / 0 / 0 | MATCH=10 | PRESERVED | 10/10 (100.0%) | 0/45 (0.0%) | 0 |
| Qwen2.5-Coder 7B | 5 / 2 / 3 | MATCH=5, FALSE_VIOLATION=2, PRESERVATION_NOT_ESTABLISHED=3 | PRESERVED | 5/10 (50.0%) | 31/45 (68.9%) | 0 |
| Llama 3.1 8B | 8 / 1 / 0 | MATCH=8, FALSE_VIOLATION=1 | PRESERVED | 8/9 (88.9%) | 8/36 (22.2%) | 1 |

## 6. Security-Significant Findings

- Qwen2.5 3B Instruct produced `UNSAFE_FALSE_PRESERVATION` on `prf-001` in 9/10 scheduled observations (9/10 valid semantic judgments).
- Qwen2.5-Coder 7B produced `UNSAFE_FALSE_PRESERVATION` on `prf-001` in 6/10 scheduled observations (6/10 valid semantic judgments).
- Qwen2.5-Coder 7B produced `UNSAFE_FALSE_PRESERVATION` on `prf-004` in 6/10 scheduled observations (6/10 valid semantic judgments).
- Qwen2.5-Coder 7B produced `UNSAFE_FALSE_PRESERVATION` on `prf-005` in 9/10 scheduled observations (9/10 valid semantic judgments).
- Llama 3.1 8B produced `UNSAFE_FALSE_PRESERVATION` on `prf-001` in 6/10 scheduled observations (6/10 valid semantic judgments).
- Llama 3.1 8B produced `UNSAFE_FALSE_PRESERVATION` on `prf-002` in 3/10 scheduled observations (3/9 valid semantic judgments).
- Llama 3.1 8B produced `UNSAFE_UNVERIFIABLE_UPGRADE` on `prf-003` in 4/10 scheduled observations (4/9 valid semantic judgments).
- Llama 3.1 8B produced `UNSAFE_FALSE_PRESERVATION` on `prf-004` in 8/10 scheduled observations (8/10 valid semantic judgments).
- Llama 3.1 8B produced `UNSAFE_FALSE_PRESERVATION` on `prf-005` in 6/10 scheduled observations (6/10 valid semantic judgments).

## 7. Cross-Model Findings

- `prf-001` / `exact_neighborhood_identity` repeated `UNSAFE_FALSE_PRESERVATION` across 3 models: Qwen2.5 3B Instruct 9/10, Qwen2.5-Coder 7B 6/10, Llama 3.1 8B 6/10.
- `prf-004` / `multiplicity_sensitive_relation` repeated `UNSAFE_FALSE_PRESERVATION` across 2 models: Qwen2.5-Coder 7B 6/10, Llama 3.1 8B 8/10.
- `prf-005` / `composed_semantic_validity` repeated `UNSAFE_FALSE_PRESERVATION` across 2 models: Qwen2.5-Coder 7B 9/10, Llama 3.1 8B 6/10.
- Semantic outcomes varied across models or within model distributions on: prf-001, prf-002, prf-003, prf-004, prf-005, prf-006.
- All models produced one identical outcome throughout on: none.
- All models matched on every scheduled valid observation on: none.
- Every model had zero matching valid observations on: none.

## 8. Semantic Stability

Frequencies below are empirical observed frequencies among valid semantic judgments, not calibrated probabilities.

| Model / challenge | PRESERVED | VIOLATED | UNVERIFIABLE | Modal share | Nonmodal rate | Pairwise disagreement |
|---|---:|---:|---:|---:|---:|---:|
| Qwen2.5 3B Instruct / prf-001 | 9 | 1 | 0 | 9/10 (90.0%) | 1/10 (10.0%) | 9/45 (20.0%) |
| Qwen2.5 3B Instruct / prf-002 | 0 | 10 | 0 | 10/10 (100.0%) | 0/10 (0.0%) | 0/45 (0.0%) |
| Qwen2.5 3B Instruct / prf-003 | 0 | 0 | 10 | 10/10 (100.0%) | 0/10 (0.0%) | 0/45 (0.0%) |
| Qwen2.5 3B Instruct / prf-004 | 0 | 10 | 0 | 10/10 (100.0%) | 0/10 (0.0%) | 0/45 (0.0%) |
| Qwen2.5 3B Instruct / prf-005 | 0 | 10 | 0 | 10/10 (100.0%) | 0/10 (0.0%) | 0/45 (0.0%) |
| Qwen2.5 3B Instruct / prf-006 | 10 | 0 | 0 | 10/10 (100.0%) | 0/10 (0.0%) | 0/45 (0.0%) |
| Qwen2.5-Coder 7B / prf-001 | 6 | 0 | 4 | 6/10 (60.0%) | 4/10 (40.0%) | 24/45 (53.3%) |
| Qwen2.5-Coder 7B / prf-002 | 0 | 8 | 2 | 8/10 (80.0%) | 2/10 (20.0%) | 16/45 (35.6%) |
| Qwen2.5-Coder 7B / prf-003 | 0 | 0 | 10 | 10/10 (100.0%) | 0/10 (0.0%) | 0/45 (0.0%) |
| Qwen2.5-Coder 7B / prf-004 | 6 | 2 | 2 | 6/10 (60.0%) | 4/10 (40.0%) | 28/45 (62.2%) |
| Qwen2.5-Coder 7B / prf-005 | 9 | 0 | 1 | 9/10 (90.0%) | 1/10 (10.0%) | 9/45 (20.0%) |
| Qwen2.5-Coder 7B / prf-006 | 5 | 2 | 3 | 5/10 (50.0%) | 5/10 (50.0%) | 31/45 (68.9%) |
| Llama 3.1 8B / prf-001 | 6 | 4 | 0 | 6/10 (60.0%) | 4/10 (40.0%) | 24/45 (53.3%) |
| Llama 3.1 8B / prf-002 | 3 | 4 | 2 | 4/9 (44.4%) | 5/9 (55.6%) | 26/36 (72.2%) |
| Llama 3.1 8B / prf-003 | 4 | 4 | 1 | 4/9 (44.4%) | 5/9 (55.6%) | 24/36 (66.7%) |
| Llama 3.1 8B / prf-004 | 8 | 2 | 0 | 8/10 (80.0%) | 2/10 (20.0%) | 16/45 (35.6%) |
| Llama 3.1 8B / prf-005 | 6 | 3 | 1 | 6/10 (60.0%) | 4/10 (40.0%) | 27/45 (60.0%) |
| Llama 3.1 8B / prf-006 | 8 | 1 | 0 | 8/9 (88.9%) | 1/9 (11.1%) | 8/36 (22.2%) |

## 9. First-Run vs Repeated-Run Comparison

Historical first-run observations are comparisons only and are not included in any fresh n=10 denominator.

| Model / challenge | Historical status | Historical outcome | Fresh recurrence |
|---|---|---|---|
| Qwen2.5 3B Instruct / prf-001 | RESPONSE_VALID | VIOLATED | RECURRED_NONMODAL |
| Qwen2.5 3B Instruct / prf-002 | RESPONSE_VALID | VIOLATED | RECURRED_MODAL |
| Qwen2.5 3B Instruct / prf-003 | RESPONSE_VALID | UNVERIFIABLE | RECURRED_MODAL |
| Qwen2.5 3B Instruct / prf-004 | RESPONSE_VALID | VIOLATED | RECURRED_MODAL |
| Qwen2.5 3B Instruct / prf-005 | RESPONSE_VALID | VIOLATED | RECURRED_MODAL |
| Qwen2.5 3B Instruct / prf-006 | MALFORMED_RESPONSE | none | HISTORICAL_ADAPTER_FAILURE |
| Qwen2.5-Coder 7B / prf-001 | RESPONSE_VALID | UNVERIFIABLE | RECURRED_NONMODAL |
| Qwen2.5-Coder 7B / prf-002 | RESPONSE_VALID | VIOLATED | RECURRED_MODAL |
| Qwen2.5-Coder 7B / prf-003 | RESPONSE_VALID | PRESERVED | DID_NOT_RECUR |
| Qwen2.5-Coder 7B / prf-004 | RESPONSE_VALID | VIOLATED | RECURRED_NONMODAL |
| Qwen2.5-Coder 7B / prf-005 | RESPONSE_VALID | PRESERVED | RECURRED_MODAL |
| Qwen2.5-Coder 7B / prf-006 | RESPONSE_VALID | UNVERIFIABLE | RECURRED_NONMODAL |
| Llama 3.1 8B / prf-001 | RESPONSE_VALID | PRESERVED | RECURRED_MODAL |
| Llama 3.1 8B / prf-002 | RESPONSE_VALID | VIOLATED | RECURRED_MODAL |
| Llama 3.1 8B / prf-003 | RESPONSE_VALID | VIOLATED | RECURRED_MODAL |
| Llama 3.1 8B / prf-004 | RESPONSE_VALID | PRESERVED | RECURRED_MODAL |
| Llama 3.1 8B / prf-005 | RESPONSE_VALID | PRESERVED | RECURRED_MODAL |
| Llama 3.1 8B / prf-006 | RESPONSE_VALID | VIOLATED | RECURRED_NONMODAL |

## 10. Adapter Reliability

Adapter status totals: `INVALID_EVALUATOR_OUTPUT`=1, `MALFORMED_RESPONSE`=2, `RESPONSE_VALID`=177. Adapter failures are not semantic outcomes. The observed failure categories were malformed output and invalid evaluator-output schema; no failed observation was retried or converted to `UNVERIFIABLE`.

## 11. Evidence Integrity

- Payload files: 1856
- Payload bytes: 4004000
- Payload inventory SHA-256: `cc508112873f76feaab08f8f1766b02716d00620bdc184157d26dde49b92eda9`
- Capture summary SHA-256: `5b7fe3224f37bf526b658ca8042ca7cb5a1a05ee9b0a3130b4a36ad030b58775`
- Repeated-run matrix SHA-256: `1bcba212948f4109a983bb706bfead927184b4d2cc1ebf8dce16cf9bf31ffe28`
- Stability summary SHA-256: `2dd4fe92b4d1095bff85da7568620add50a0a45abb804da60fac74c49e7c00d2`
- Cross-model summary SHA-256: `fdbeb4b4ec4a05bbe843d23eed1c8657cd174d6e68f9f8056252a11b70ce1b66`
- Validator result: required to pass in CI.
- Mutation controls: 19 required fail-closed mutations.
- Secret scan: zero actual credentials detected; detector-source literals are not credentials.

## 12. Interpretation and Limits

These results characterize the recorded repeated blind observations under the frozen PRF v0 benchmark and recorded evaluator configurations. They do not establish universal model behavior, deterministic semantic outcomes, statistical significance by themselves, or external-domain truth beyond the benchmark authority.

Model size is not itself evidence of semantic capability. Benchmark-relative mismatches apply only to these recorded invocations. Committed transcripts bind the observations but do not guarantee replay by a nondeterministic evaluator.

## 13. Reproduction

```text
python tools/validate_external_evaluator_repeated_evidence.py
python tools/validate_v0_freeze.py
python -m unittest discover -s tests -v
python -O -m unittest discover -s tests -v
```

Raw observations are under `evidence/external-evaluators/v0/repeated-runs/payload/<model>/<challenge>/run-XX/`. Evaluator-side reproduction consumes only blind requests and does not require oracle access; benchmark scoring is a later, separate step.

## 14. Next Work

- additional model families
- community external runs
- larger repeated-run sample sizes
- agent/tool-use evaluation
- later standardization/ERC consideration
