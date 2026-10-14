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
