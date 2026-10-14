# Architecture — Milestone 1

`app.py` provides only upload/demo controls, presentation, and session-memory storage. Public `import_file(bytes, filename, limits)` and `import_batch(sequence[ImportInput], limits)` interfaces accept typed inputs and return immutable `ImportResult` models. Core modules never import Streamlit or read session state.

Data flow: bounded input → standard-library CSV/JSON or restricted Markdown parser → strict record validation → immutable source artifact/inventory with original metadata and provenance → source-preserving normalization → validation summary.

`models.py` defines schema versions, source identities, provenance, review states, validation issues, and future source-referenced claim containers. `importers.py` validates file structure and budgets and preserves accepted original records. `normalizer.py` copies supported fields without interpreting status as customer impact, deployment, or approval. `config.py` safely loads local resource configuration with PyYAML. No classifier, AI writer, impact engine, database, or placeholder adapter is introduced.

Internal keys disambiguate IDs across files/types/record positions without changing original IDs. Related IDs stay explicit. Reference presence establishes provenance, not semantic proof. Future generation will require a replaceable Ollama adapter, source-reference validation, and human editorial review. No claims, documentation impacts, or generated release notes are created in this milestone.

Specification: docs/PRD.md contains the formal PRD supplied in sprint2doc-prd.md. The original file is preserved. This milestone deliberately implements only the Foundation exit criterion; full-v1 acceptance criteria concerning generation and publication belong to later milestones.
