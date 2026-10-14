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


## Instruct-model live validation follow-up

With explicit user approval, `qwen3-vl:4b-instruct` was installed locally; the prior
30B model's files were retained. Digest:
`ee4b975b58c17ce268cd19d40db35d5edc64603035d2ffc1fee1968eb0947f7b`.
The one-ticket HarborDesk quick-start ran through `generate_release` and the real
Ollama adapter with a 300-second timeout, 1,200 output-token limit, 8,192 context
tokens and one record per batch. It returned complete status, two pending claims,
one unresolved clarification question, zero held claims and no diagnostics.
Original source IDs and exact excerpts passed deterministic validation.

Elapsed time was about 251 seconds. This overlapped with the previous app generation,
and both models were initially loaded on CPU; the 30B model was unloaded from RAM
without deleting its installed files. This is not an isolated performance benchmark.
The full FleetOps release was not rerun during this follow-up. The app's batch-size
setting processes the selected release sequentially rather than selecting only one record.

Human inspection remains required: for example, the model added “preserving original
data integrity” to a timestamp statement, a broader inference than the cited excerpt
establishes. Valid citations do not establish semantic correctness or deployment.


## Review workflow and validator 1.1 follow-up

October 14, 2026: 96 tests passed, including saved-review restoration, pending queue
filtering, and numeric source-ID regression cases. Ruff, format checks, strict mypy,
uv lock consistency and git whitespace checks passed. The frozen-dependency audit
reported no known vulnerabilities. Validly cited whole alphanumeric IDs are exempted
from quantity checking; invented quantities, uncited IDs and identifier prefixes remain
flagged. Existing session drafts retain their original validation results.


## Editorial review and export verification

October 14, 2026: 114 tests passed. New tests cover explicit approval, material-edit
approval reset (text/category/audience/evidence), held/rejected-note exclusion, stale
snapshot gating, separate human answer attribution, duplicate candidates, complete
JSON round-trips, nested source references, fixed ZIP paths, inert Markdown/HTML,
and Streamlit editing/approval/download behavior without model calls. Ruff, formatting,
strict mypy (12 core modules), lock consistency, whitespace and dependency audit passed;
no known advisories were reported. Browser/native printer output was not exercised;
HTML structure, print CSS and no-active-markup behavior were checked programmatically.
Documentation impact generation remains outside this reporting change.
