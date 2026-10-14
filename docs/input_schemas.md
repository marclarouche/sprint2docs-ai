# Supported input schemas (version 1.0)

Only the schemas below are supported; arbitrary Jira/GitHub exports are not. All files use strict UTF-8, optionally with a BOM. Filename extensions select `.csv`, `.json`, or `.md`; uploaded paths are never opened. Source URLs are strings, never fetched.

## CSV tickets

Headers are case-sensitive. `id` and `title` are required and must be nonempty; IDs cannot contain whitespace. Supported optional headers are `description`, `status`, `release_id`, `change_type`, `component`, `related_ids`, `labels`, and `url`. Optional empty CSV cells map to unknown (`None`), with validation warnings. Semicolons delimit `related_ids` and `labels`; quote CSV fields normally for commas/newlines. Standard-library strict CSV parsing rejects duplicate/blank headers, ragged rows, and malformed quoting. The parser's default single-field limit is 128 KiB.

```csv
id,title,description,status,release_id,related_ids
FLEET-142,Add MFA enrollment,TOTP enrollment workflow,done,2.4.0,PR-204
```

Original CSV cell values are retained as immutable JSON text before conversion. Unknown columns are retained and identified, with a metadata warning. Logical record numbers are one-based, excluding the header; physical start/end lines cover quoted multiline records. The filename and SHA-256 identify the uploaded file bytes.

## JSON tickets and pull requests

The envelope requires `schema_version: "1.0"`, `artifact_type` equal to `ticket` or `pull_request`, and a nonempty `records` array. Each record requires string `id` and string `title`. Optional fields match CSV, but `related_ids` and `labels` must be JSON arrays of nonblank strings, or null. Numbers/booleans are not coerced into strings. Absent/null/empty optional strings produce warnings. An explicit empty array represents a supplied empty list and is preserved.

```json
{"schema_version":"1.0","artifact_type":"pull_request","records":[
  {"id":"PR-204","title":"Add MFA enrollment","description":"TOTP workflow",
   "status":"merged","release_id":"2.4.0","related_ids":["FLEET-142"]}
]}
```

Duplicate JSON object keys, NaN/Infinity, excessive nesting, unsupported versions/types, and malformed envelopes are rejected. Unknown record metadata is retained in `original_record_json` and listed in `unrecognized_fields`. Unknown envelope metadata is retained once per file in `envelope_metadata_json`. Metadata is never used as commands or trusted instructions. JSON records have one-based array positions; JSON physical line locations are not available. Canonical JSON preserves values, not source whitespace/key order; SHA-256 identifies exact original bytes.

## JSON documentation inventory

Use the same envelope with `artifact_type: "documentation_inventory"`. Each entry requires string `document_id` and string `title`. Optional fields: string `document_type`, string `component`, string `description`, array-of-string `covered_features`, and array-of-string `section_ids`. Missing optional fields produce warnings. Entries remain inventories, not product changes. Unknown metadata is preserved as for other JSON records.

```json
{"schema_version":"1.0","artifact_type":"documentation_inventory","records":[
  {"document_id":"DOC-SEC-001","title":"Authentication guide",
   "document_type":"administrator_guide","component":"identity",
   "covered_features":["MFA"],"description":"Enrollment procedures","section_ids":["enrollment"]}
]}
```

## Markdown changelog

Use a restricted explicit grammar, not arbitrary Markdown:

```markdown
# Fictional FleetOps Demo changelog
## [2.4.0]
### Added
- [CL-240-01] Administrator MFA enrollment
  Adds an enrollment workflow. Enforcement policy is not specified.
  Related: FLEET-142, PR-204
```

Release headings must be `## [release]` or `## release` without a date suffix; categories may use `### category`. Entries require `- [original-ID] title`. Description continuation lines require at least two leading spaces. An optional indented `Related:` line uses comma-separated IDs. Each entry retains its literal Markdown block, source line range, explicit release, and category. Categories are copied exactly, not classified. A top-level `# title` is structural display context, not an artifact field; its exact bytes remain identifiable through the file hash. Fenced code/freeform sections and bullets without IDs are rejected rather than silently interpreted. Missing description/status/component/etc. produce warnings.

## Errors, limits, and import decisions

Invalid encoding, file structure, or resource limits reject that file. Invalid records reject those records while retaining valid neighbors; `records_seen` counts all schema-shaped rows including rejected records. Batch byte/text/file budgets are checked before any records are accepted; a record-limit rejection stops later file processing. Empty files and empty record collections are rejected.

Defaults: 10 MiB/file, 25 MiB/batch, 10 files, 2,000 records, 2,000,000 decoded characters per batch, and JSON depth 20. Character budgets include metadata and formatting, which is stricter than counting extracted semantic text alone. Limits in `config/import_limits.yaml` can be lowered; hard ceilings bound overrides.

Normalization is one record to one change. Source IDs and explicitly supplied references survive unchanged; generated internal keys are SHA-256(file hash + kind + record number), and change IDs derive from them. Identical bytes/position yield the same stable key, including repeated identical-file uploads; different records with the same original ID have distinct keys. Unknown/missing values do not become invented classifications. `pending` is an application editorial state, not an inferred source status. Empty claims/impact links mean those analyses have not been performed.

Explicit associations are represented by `related_ids`, not yet resolved or merged. Duplicate original IDs produce warnings; title similarity and conflicting-content analysis are deferred to Milestone 2. These schema and partial-import choices are documented implementation decisions where the PRD did not prescribe a wire format.
