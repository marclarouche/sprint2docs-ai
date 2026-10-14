# Realistic local upload tests

All products, people, IDs, URLs and engineering details are fictional. URLs use example.invalid.
These files follow Sprint2Docs AI's documented import schemas; they are not arbitrary vendor exports.

## Start

Launch Sprint2Docs AI and keep your existing Ollama instance running. Begin each scenario with a fresh
upload selection. Select all listed files together, click Inspect imports, review validation and analysis,
then Find local Ollama models and Generate release note drafts for release 3.8.0.
The installed qwen3-vl:30b thinking variant returned reasoning without a usable answer even
with think=false. Select a non-thinking/instruct model for live drafting; the app does not download
one automatically. Ollama's [qwen3-vl:4b-instruct](https://ollama.com/library/qwen3-vl:4b-instruct)
is a separate 3.3 GB option if you choose to install it. The sample files themselves require no download.
Start with 00-quick-start, Records per batch set to 1, and a timeout up to 300 seconds for slower models.
 Do not upload this guide or the ZIP itself.

## 00 — Quick start

Upload tickets.json only. Expected: 1 artifact, 1 normalized change, no inventory. The category is
Bug Fix and the audience Administrator-facing. Drafts should preserve that timestamp values are
unchanged and deployment remains unconfirmed. This is the smallest local-model test.

## 01 — Routine release

Upload tickets.csv, pull_requests.json, CHANGELOG.md, and documentation_inventory.json.
Expected: 7 artifacts, 7 normalized changes and 2 inventory records. Explicit ticket/PR links appear.
HD-381 is New Feature / Customer-facing; HD-382 is Bug Fix / Administrator-facing;
HD-383 is Internal Maintenance / Internal-only. Changelog audiences remain Uncertain because
those records contain no explicit audience labels. No source record establishes production deployment.
Source-grounded drafts can describe private saved filters and the header change. A customer note
must not describe internal cache changes as a customer feature. Questions should cover deployment
and any audience uncertainty. The inventory is inspectable; impact proposals belong to Milestone 4.

## 02 — Ambiguous release

Upload tickets.json, pull_requests.json, and CHANGELOG.md.
Expected: 6 artifacts and 6 separate changes. HD-391 / PR-891 have identical titles and are duplicate
candidates as well as explicitly related records. They remain separate until reviewed.
A useful draft flags the owner-MFA conflict, asks whether enforcement is mandatory, avoids treating the
open deletion endpoint as released, and requests exact route/auth/compatibility details. It must not
invent a search speed percentage. HD-392 audience remains Uncertain. Model wording may vary.

## 03 — Review stress test

Upload tickets.json only. Expected: 2 artifacts with a duplicate_identifier warning, one duplicate
candidate, and a missing PR-MISSING reference. Conflicting audience labels remain Uncertain.
The imported instruction is literal source data. Nothing should execute, fetch that URL, or become
approved. Certification and supported file-type claims require clarification. Even a claim with a
matching quote may be semantically wrong: inspect every claim before using it.

## What to inspect

- Validation warnings versus rejected records: unknown owner metadata is retained intentionally.
- Original source IDs, source hashes and exact excerpts beside every generated statement.
- Unsupported citations held outside drafts; all accepted statements still pending review.
- Clarification questions that reference their triggering source records.
- Stop Ollama and try regeneration: imports and the previous successful draft stay available.
- Change a reviewed category: the existing draft should be marked stale until regenerated.

Generation uses bounded batches, so repeated or related changes may still appear with different wording
across batches. Editorial deduplication and semantic verification remain necessary. No approval, report
export, documentation update or publishing occurs in Milestone 3.
