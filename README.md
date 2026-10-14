# Sprint2Docs AI — Milestone 3

Local-first import, reviewable change analysis, and source-referenced customer and technical release note drafts using local Ollama. Every generated statement remains pending editorial verification.

## Install (Python 3.12)

Install Python 3.12 and [uv](https://docs.astral.sh/uv/getting-started/installation/), then from this directory:

```sh
uv sync --frozen --python 3.12
uv run --frozen --offline streamlit run app.py
```

If uv is not already installed, a project-local bootstrap is supported:

```sh
python3.12 -m venv .tools
.tools/bin/python -m pip install uv==0.13.1
.tools/bin/uv sync --frozen --python 3.12
.venv/bin/streamlit run app.py
```

On Windows, use `py -3.12 -m venv .tools`, `.tools\Scripts\python.exe -m pip install uv==0.13.1`, `.tools\Scripts\uv.exe sync --frozen --python 3.12`, then `.venv\Scripts\streamlit.exe run app.py`.

`uv.lock` pins resolved runtime and development dependencies with distribution hashes. Installation and vulnerability scanning require internet access; inspection and local-model drafting do not. Development tools are installed by default; `uv sync --frozen --no-dev` installs only runtime dependencies. Run from the repository root so Streamlit loads its localhost/telemetry configuration.

## Use

Click **Load fictional FleetOps 2.4.0 demo**, or upload supported CSV, JSON, and Markdown files together and click **Inspect imports**. Inspect validation issues, original artifacts, normalized changes, and inventory. Successful records remain available when another record fails; the UI clearly marks partial imports. No inspection data is written to disk. Changing uploads clears previous results.

The demo produces 9 source artifacts, 9 separate normalized changes, and 2 inventory entries. Repeated source IDs remain separate review candidates. Explicit related IDs form reviewable associations; shared IDs and matching titles form duplicate candidates. Records are never automatically merged. A `done` ticket or `merged` PR does not establish release/deployment evidence.

## Headless interface

```python
from sprint2docs import ImportInput, import_batch, import_file

result = import_file(b"id,title\nFLEET-1,Example change\n", "tickets.csv")
print(result.error_count, result.warning_count)
assert result.changes[0].source_references[0].artifact_id == "FLEET-1"
```

Public models and interfaces are in `src/sprint2docs/`; Streamlit is confined to `app.py`. Imported contents, URLs, markup, and instructions remain untrusted data. Original IDs, metadata, source hashes, and record locations are preserved. Missing optional values stay unknown and produce warnings, not invented source facts.

## Verify

```sh
uv run --frozen --offline pytest -q
uv run --frozen --offline ruff check .
uv run --frozen --offline ruff format --check .
uv run --frozen --offline mypy
uv export --frozen --no-emit-project --format requirements-txt --output-file /tmp/sprint2docs-audit.txt --quiet
uv run --frozen pip-audit --disable-pip --no-deps -r /tmp/sprint2docs-audit.txt
```

The application smoke test is included in pytest. Tests deny socket connections, URL fetching, and shell subprocesses. pip-audit queries package advisory services using dependency names/versions only; it does not process source artifacts. Mypy strictly checks core modules. The current environment and measured results are recorded in `docs/verification.md`.

## Documentation and scope

- `docs/PRD.md`: formal PRD preserved from the supplied `sprint2doc-prd.md`; future milestones remain out of scope.
- `docs/input_schemas.md`: exact supported schemas and parsing rules.
- `docs/architecture.md`: layering, source identities, and adapter boundaries.
- `docs/security.md`: untrusted-input policy, bounded resource limits, and remaining risks.
- `AGENTS.md`: engineering constraints for subsequent work.
- `samples/fleetops_demo/`: clearly fictional valid data.
- `tests/fixtures/`: invalid and malicious-as-data samples.

## Draft with local Ollama

Start your installed Ollama instance with an existing local model. No model is downloaded automatically. The locally tested `qwen3-vl:30b` thinking variant
returned reasoning without a usable answer; select an instruct variant for live validation.
Load the demo, inspect analysis, then click **Find local Ollama models**. Select a non-thinking/instruct model and release,
adjust the timeout if needed, and click **Generate release note drafts**.
The adapter uses only `127.0.0.1:11434`; cloud model names and remote model entries are excluded.
Review customer and technical statements beside their exact source excerpts. Invalid citations
are held outside release note drafts. Clarification questions identify missing engineering facts.
Matching references do not prove semantic correctness or deployed behavior.

Generation is bounded to 40 release records, four per batch, 24,000 context characters per batch,
and 3,000 predicted output tokens by default. No automatic retries. UI timeout defaults to 120 seconds.
Headless callers can configure `GenerationSettings` and the adapter's loopback port.
Failed batches preserve successful batches; a completely failed attempt preserves the previous draft.
New imports clear drafts. Analysis changes mark earlier drafts stale. Session data is not persisted.

See `docs/milestone2.md` and `docs/milestone3.md` for rules, validation, limits and measured results.
Next milestone: documentation impact and update proposals. Editorial approval workflows and
report exports remain later milestones.
