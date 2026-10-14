# Milestone 1 measured verification

Checked October 14, 2026, using CPython 3.12.14, uv 0.13.1, and the committed uv.lock environment on macOS. Other operating systems have installation instructions but were not executed here.

| Check | Actual command (from project root) | Result |
| --- | --- | --- |
| Install | `uv sync --frozen --python <Python-3.12 interpreter>` | Locked runtime and dev dependencies installed |
| Tests and application smoke | `.venv/bin/python -m pytest -q` | 45 passed; includes Streamlit initial render and fictional-demo inspection with network/shell calls blocked |
| Lint | `.venv/bin/ruff check .` | Passed |
| Formatting | `.venv/bin/ruff format --check .` | Passed |
| Strict core typing | `.venv/bin/mypy` | Passed, five core modules |
| Lock consistency | `uv lock --check` | Passed |
| Dependency audit | `uv export --frozen --no-emit-project ...`, then `pip-audit --disable-pip --no-deps -r <exported pinned requirements>` | 69 dependency records audited; zero known advisories, no skipped records |

Early checks found a CSV return-type annotation and a union-narrowing issue in batch inventory handling; both were corrected. Initial Ruff style issues were fixed and checked. No requested check remains blocked. pip-audit made package-metadata requests to PyPI; normal processing was verified with network/subprocess operations denied. The advisory result is a point-in-time check, not a guarantee of security.

The smoke test exercises the local UI and demo, not an end-to-end browser upload or a running HTTP server. Invalid data, invalid UTF-8, 10 MiB overflow, record/text/depth/batch limits, partial record acceptance, original metadata, provenance, immutable models, duplicate candidates, YAML safety, and malicious-as-data strings are covered. Original artifacts are not executed. No generated claims or release notes are produced.

Known limitations: documented schemas only; restricted Markdown grammar; no inferred classification, similarity matching, relationship resolution, impact analysis, AI adapter, or persistence. Missing optional fields produce potentially numerous warnings. Record validation supports partial success; users must review rejection summaries before any future drafting. Original rejected file bodies are not echoed into diagnostics; retain the upload externally if it requires correction. See input_schemas.md for resource-budget and canonicalization decisions.

# Milestones 2 and 3 measured verification

Checked October 14, 2026 in the existing Python 3.12 locked environment on macOS.

- Full suite: 85 passed. Includes deterministic analysis, immutable provenance, review/reset,
  bounded AI schemas/context, invalid citation/excerpt rejection, batch-local references,
  partial/empty failures, local-only transport and cloud-entry exclusion, UI draft preservation,
  and all four realistic upload scenarios.
- `ruff check .`, `ruff format --check .`, and strict `mypy`: passed.
- `uv lock --check`: passed; no dependency changes were needed for the standard-library adapter.
- Frozen dependency export plus `pip-audit --disable-pip --no-deps -r ...`: no known vulnerabilities.
- Deliverable ZIP integrity checked; it contains ten files including the upload guide.

Live Ollama was reachable at literal loopback. Installed model: `qwen3-vl:30b`, digest
`eda0be1008774ea4e575187712b9a3b1201f3e66e7ecff899cc295db1cf00248`.
Ollama's running-model metadata reported CPU execution (`size_vram: 0`).
A full fictional FleetOps release attempt, four records per batch and 2,000 predicted output tokens,
timed out on all three requests at 180 seconds per request. It produced no usable drafts.
This is a failed live generation check, not evidence that the sample release was generated.
Service failure handling was verified independently by deterministic tests; import state remains available.

The first one-ticket quick-start attempt used an 8,192-token context, 1,000 output-token
limit and 300-second request timeout. It reached the output limit after about 223 seconds,
and was rejected as incomplete. Response schemas were then tightened to at most two claims
and one question per source, with shorter text/excerpt limits. A final run is recorded below.

The final tightened one-ticket attempt (1,200 output tokens, 8,192 context tokens,
300-second timeout) hit the output limit after about 213 seconds with no usable draft.
A bounded 128-token diagnostic then returned zero answer characters and 625 reasoning
characters despite `think:false`. Ollama version was 0.40.3. This identifies a model
compatibility limitation, not merely CPU speed. The adapter now reports reasoning-only
responses with a specific instruction to select a non-thinking/instruct model; reasoning
is never treated as release content or exposed in diagnostics.

Ollama maintainers state that Qwen3-VL thinking variants are not hybrid models and cannot
disable reasoning: https://github.com/ollama/ollama/issues/16945 . The installed model's
reported thinking toggle values did not match its observed behavior. Live generation
with the installed model did not pass. No different model was downloaded or installed.
A non-thinking/instruct model remains necessary for the next live validation attempt.

The four upload scenarios pass structural and deterministic analysis checks. Their AI
wording and semantic accuracy still require evaluation with a compatible model and human review.
