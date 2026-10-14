# Security and privacy

Normal application processing is local and in memory. `.streamlit/config.toml` binds to 127.0.0.1, limits individual uploads to 10 MiB, and disables Streamlit usage telemetry. Launch from the repository root. The only application HTTP transport is the dedicated Ollama adapter on literal IPv4 loopback. It uses fixed `/api/tags` and `/api/chat` paths, ignores proxy environment variables, and does not follow redirects. No imported URLs are fetched, shell commands invoked, source scripts run, or imported HTML rendered as HTML. Imported strings are displayed with JSON/table widgets; never use unsafe HTML rendering for them.

File names are reduced to a printable basename for presentation and provenance; they never select filesystem paths. Only the trusted fictional-demo button reads fixed repository paths. Unknown input metadata may contain secrets and is retained intentionally for traceability; it is never logged. Full record values are only visible within the local inspection UI/session. Do not share screenshots or inspection dumps containing proprietary input without review.

CSV/JSON parsing uses Python standard-library parsers. JSON duplicate keys and nonfinite numbers are rejected, nesting is bounded, and strings are never evaluated. CSV formulas and prompt-injection instructions remain literal data. YAML is used only for local configuration via safe_load, with bounded reads and Pydantic validation. Uploads do not support YAML, DOCX, archives, pickle, or executable types.

Core size/count/text/depth budgets are enforced independently of Streamlit. Raw decoded text (including metadata) counts toward character limits. These are parsing/resource controls, not an isolated parser sandbox or protection against all browser-side upload memory pressure. CSV additionally has Python's default 128 KiB single-field cap. The app supports only a single local user and is not prepared for public hosting or adversarial concurrent users.

Expected validation errors use static codes and safe field names, never raw exception text or input excerpts. The UI shows generic failure messages and reviewable validation summaries. Unexpected UI errors log only subsystem and exception class, no traceback, filename, secret, or imported text. Accepted original records are immutable strings and provenance uses tuples/frozen models. Changing uploads or closing a session drops its result; restarting the process clears in-memory sessions. Python memory is not securely erased, and browser/OS memory management is outside this app's control.

Tests deny network connections, URL fetches, and subprocess execution, and exercise malicious strings without executing them. Installation and pip-audit use networking outside normal application processing. pip-audit sends dependency package metadata only. A clean audit means no known advisories were reported by the queried service at check time; it does not prove absence of vulnerabilities. The uv lock pins runtime/dev dependencies and hashes; keep it updated when advisories emerge.


Milestone 3 adds constrained AI drafting: local model availability checks, cloud-name and remote-entry filtering,
Pydantic response schemas, byte and token limits, bounded context batches and request timeouts.
There are no model tools and no automatic retries, model downloads, approval or publishing.
Only the local Ollama adapter may import HTTP/socket facilities. Tests replace this transport and retain
network/subprocess denial for all test cases. Installed-model metadata and selected source fields go only
to local Ollama. A separately configured or modified Ollama installation is outside the application's control.

Prompt isolation is defense in depth, not a guarantee that a model will ignore malicious source text.
Model output is data with no execution capability. Exact source keys, original IDs and excerpt membership
are validated against the request batch. Unsupported references and unmatched numeric details are held.
These checks do not establish semantic entailment, availability or accuracy. Every accepted statement is
explicitly pending human verification. Generated text is displayed as text/JSON, not active HTML.
