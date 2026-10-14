# Milestone 3: Local AI drafting

## Use

Start your existing local Ollama service. Inspect imports or load the FleetOps demo.
Click Find local Ollama models, select an installed model and a release, then Generate
release note drafts. No model is pulled automatically. The built-in adapter connects
only to literal IPv4 loopback on port 11434; headless callers may configure the port.
The UI supports local model selection, request timeout (1–300 seconds), records per batch (1–8),
and output token limit (128–8,000). It displays the current batch number while drafting.
Smaller batches can help slower models; overly low output limits can produce rejected truncated output.

Customer and technical statements remain drafts with pending review. Each statement
shows original source IDs, exact title/description excerpts and file provenance.
Invalidly cited statements are held outside the release notes. Clarification questions
reference source evidence and remain unresolved. Matching excerpts do not establish
semantic support, deployment or truth; inspect every generated claim.

## Boundaries and limits

- Release selection is exact. Records with other or missing release IDs are excluded visibly.
- Default generation limit: 40 records, 4 records and 24,000 source-context characters per batch.
- UTF-8 byte counts additionally enforce a conservative context-token budget including the system
  prompt, schema, output allowance and message overhead. Batches may split below the record limit.
- Oversized individual records are rejected before generation; sources are never silently truncated.
- Default output: 3,000 predicted tokens, 16,384 context tokens, temperature 0 and seed 42.
- HTTP responses are bounded to 256,000 bytes; generated content to 128,000 bytes.
- Default timeout: 120 seconds per request. No automatic retries (zero retries is bounded).
- The model receives title, description, status, related IDs and current reviewed analysis, not
  arbitrary unknown metadata, URLs or entire raw source files.
- A strict response schema allows at most two claims and one clarification question per source
  in each request, with at most three evidence excerpts per item and 500 characters per text/excerpt.
- Citation validation checks keys against the current batch, original IDs and exact excerpt membership.
  A narrow guard holds unmatched numeric details, unverified inline-code procedures and customer
  notes citing sources classified Internal-only. It does not
  prove semantic entailment or catch every unsupported assertion.
- Failed batches preserve successful results and return partial status. Fully failed attempts preserve
  the previous successful draft. Empty batches and rejected imports are reported visibly.
- Exact duplicate claim text within an audience is shown once. Differently worded duplicates across
  batches still require editorial review. Original records are never merged.
- Metadata records model digest, settings, creation timestamp, prompt/validator/schema versions,
  source keys and hashes of import/analysis snapshots.
- New imports reset drafts. Analysis edits mark existing drafts stale until regeneration.

The replaceable `WriterAdapter` protocol separates the generator from HTTP. The adapter uses
Ollama `/api/tags` and nonstreaming `/api/chat` with a JSON schema, no tools and `think:false` requested. Some thinking-only models ignore
that setting; reasoning-only responses are rejected with a compatibility message.
Cloud model names and remotely backed model entries are excluded. Responses containing tool calls,
truncated output or invalid structures are rejected with content-free diagnostics.

Sources: [Ollama chat API](https://docs.ollama.com/api/chat) and
[structured outputs](https://docs.ollama.com/capabilities/structured-outputs).

## Scope

This milestone implements release note drafts and source-referenced clarification questions.
Question resolution with separately attributed answers, editorial approval/editing, documentation
impact and exports remain later milestones. No generated output is executed or published.
All source and generated text stays in session memory during normal application operation.

## Local upload examples

`samples/local_uploads` contains four clearly fictional, schema-compatible scenarios and a
TEST-GUIDE.md: one-ticket quick start, routine release, ambiguous release and review stress test. Upload the files inside
one scenario folder, not the guide or ZIP. Expected counts and review observations are documented.


## Installed-model limitation

On the tested local installation, `qwen3-vl:30b` consumed its output budget in reasoning and
returned no usable answer even with `think:false`. Use a non-thinking/instruct variant for
further local validation. The application does not automatically download models.
See verification.md for the failed live checks and the upstream maintainer explanation.
