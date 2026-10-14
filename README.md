# Sprint2Docs AI — Milestone 1

A local-first foundation for source-grounded release documentation. This milestone imports, validates, and normalizes tickets, pull requests, changelogs, and documentation inventories. It does **not** generate release notes, infer deployed behavior, classify changes, or call an AI model.

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

`uv.lock` pins resolved runtime and development dependencies with distribution hashes. Installation and vulnerability scanning require internet access; application inspection does not. Development tools are installed by default; `uv sync --frozen --no-dev` installs only runtime dependencies. Run from the repository root so Streamlit loads its localhost/telemetry configuration.

## Use

Click **Load fictional FleetOps 2.4.0 demo**, or upload supported CSV, JSON, and Markdown files together and click **Inspect imports**. Inspect validation issues, original artifacts, normalized changes, and inventory. Successful records remain available when another record fails; the UI clearly marks partial imports. No inspection data is written to disk. Changing uploads clears previous results.

The demo produces 9 source artifacts, 9 separate normalized changes, and 2 inventory entries. Repeated source IDs remain separate review candidates. Related IDs are copied without automatic merging or inferred associations. A `done` ticket or `merged` PR does not establish release/deployment evidence.

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
- `docs/architecture.md`: layering, source identities, and explicitly deferred analysis.
- `docs/security.md`: untrusted-input policy, bounded resource limits, and remaining risks.
- `AGENTS.md`: engineering constraints for subsequent work.
- `samples/fleetops_demo/`: clearly fictional valid data.
- `tests/fixtures/`: invalid and malicious-as-data samples.

Next milestone: explicit artifact association and duplicate proposals, reviewed change classification, and completeness analysis. Local Ollama generation remains Milestone 3 behind a separate adapter.
