# Architecture — Milestone 3

`app.py` owns controls, presentation and in-session state. `src/sprint2docs` contains the
UI-independent processing engine. Immutable models preserve original identifiers, records,
unknown metadata, file hashes and record locations.

Data flow: bounded import → normalization → deterministic analysis → release selection →
bounded AI context batches → replaceable local Ollama adapter → structured output validation →
source excerpt validation → pending customer/technical drafts and clarification questions.

`models.py`, `importers.py`, `normalizer.py`, and `config.py` implement ingestion.
`analysis.py` adds reviewable associations, duplicate candidates, categories and audiences.
`generation_models.py` defines strict, bounded response and result schemas.
`ai_writer.py` selects release records, assembles source context, handles independent batch failures,
and records prompt/validator versions, settings, model digest and source/analysis snapshots.
`ollama_adapter.py` implements the `WriterAdapter` protocol using standard-library HTTP on literal
loopback only. It performs no source URL fetching, tool execution or automatic model downloads.
`claim_validator.py` resolves original IDs and exact excerpts to imported record provenance.

Invalid model output is omitted with safe diagnostics. Invalidly cited claims remain held for
clarification, outside note drafts. Valid citations still require semantic verification by a human.
No analysis or draft modifies original sources. New imports clear drafts; changes to reviewed
analysis mark prior drafts stale. Completely failed regeneration keeps the last draft available.

Documentation impact, editorial approval and exports remain later milestones. Nothing is
published or persisted automatically. See milestone3.md for generation limits and operation.
