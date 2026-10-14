# Milestone 2: Change analysis

Load the fictional demo or inspect imports to see deterministic change analysis.
Each imported record retains its own normalized change, original data and immutable provenance.
No records are automatically merged. All suggestions begin pending human review.

Classification maps explicit `change_type` values to the nine PRD categories.
Recognized aliases include `added`, `fixed`, `changed`, `feature`, and `security`.
Missing or unrecognized types remain Unknown. Source descriptions and instructions
are never executed or interpreted as commands.

Audience comes only from explicit labels: `customer-facing`, `administrator-facing`,
`developer-facing`, or `internal-only`. Missing or conflicting labels remain Uncertain.
Completion, a security label, and title wording do not establish audience or deployment.

Associations use explicit related IDs. Repeated source IDs and identical normalized
titles within the same release produce duplicate candidates. Explicit links with
multiple targets remain visibly ambiguous. Missing targets and release conflicts are
reported. Each relationship shows source keys, reasons and a human review decision.
Shared IDs across releases remain candidates requiring review, never automatic merges.

Use Change to review to select a record, choose its category, audience and decision,
and enter a review note. Original deterministic rationales and source references remain
available. Save relationship decision records confirmation or rejection without removing
evidence. Importing new files or reloading samples resets analysis decisions. All state
remains in the current Streamlit session.

Analysis metadata records deterministic rule version 1.0. Every finding references its
original record's `change_type` and `labels`; source keys resolve to imported artifacts
with filenames, hashes and record locations. Evidence references do not verify software
behavior. This milestone has no Ollama generation or report exports.

Validation includes relationship ambiguity, conflicting releases, unsupported types,
injected source text, audience conflicts, immutable source preservation, human review,
fictional expected outcomes, and Streamlit review/reset smoke tests.


The change-review selector defaults to Pending records. Saving Approved, Rejected or
Needs Clarification removes that record from the pending queue without deleting it.
Turn on Show saved reviews to inspect or revise every saved decision. Status, audience,
category and note are restored when revisiting a record; labels include source file and
record number to distinguish similar tickets, PRs and changelog entries. Saving Pending
keeps the record in the queue. The screen confirms saves and shows the pending count.
