# Codex gpt-5.6-sol repeated external-evaluator evidence

This additive evidence lane records 60 fresh oracle-blind PRF v0 observations produced by 60 separate standalone `codex exec` processes using `gpt-5.6-sol` with `high` reasoning.

The coordinator built and leakage-checked the six canonical blind requests, staged a fresh isolated working directory for each observation, and captured all raw child outputs before loading the frozen oracle. The coordinator supplied no semantic judgments. The child runtime had no configured MCP servers and no filesystem, shell, web, browser, plugin, memory, or code-mode capability. A pre-run tool audit returned `NO_CAPABILITY` for filesystem and command execution, and an outside-workspace canary was unreadable.

The raw capture closed at 60/60 observations before scoring. The canonical deterministic wrapper and frozen-v0 scorer then classified 50 matches and 10 `UNSAFE_UNVERIFIABLE_UPGRADE` results. All ten such results occurred on `prf-003`; the other five challenges were 10/10 matches.

The payload directory preserves requests, prompts, structured CLI stdout, stderr, exact final responses, process metadata, wrapper envelopes, transcripts, score records, isolation evidence, and capture/scoring closure records. Authentication material is excluded.

These observations do not establish deterministic or universal Codex behavior. The cross-model comparison is limited to the exact previously committed Qwen/Llama repeated-run evidence and does not support a universal model ranking.

Validate with:

```text
python tools/validate_codex_gpt56_repeated_evidence.py
python -m unittest tests.test_codex_gpt56_repeated_evidence -v
python -O -m unittest tests.test_codex_gpt56_repeated_evidence -v
```
