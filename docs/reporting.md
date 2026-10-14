# Editorial review and local reports

Existing generated results can be reviewed and exported without another Ollama request.
Analysis review and generated-wording review are separate. All generated statements begin pending.

1. Enter a reviewer name. Inspect potential duplicate pairs, source excerpts and review warnings.
2. Select a NOTE, edit wording/category/audience and choose one to three existing source excerpts.
3. Save wording changes. Material changes reset approval to Pending and require a fresh decision.
4. Compare the wording with evidence, enter a decision note, and explicitly confirm verification
   before approval. Unsupported claims cannot be approved. Reject unwanted duplicates explicitly.
5. Optionally answer clarification questions; answers retain human attribution and do not become
   original imported evidence or automatic proof of the generated statements.
6. Enter a product name and choose Draft or Approved statements only under Download reports.

Downloads: full/customer/technical Markdown, complete analysis JSON, traceability JSON,
print-friendly HTML, or a ZIP containing all reports. Open HTML in a browser and press Command+P
on Mac or Control+P on Windows/Linux to print/save as PDF. There is no automatic publishing.
HTML uses escaped text, no scripts or external resources, and print CSS. Markdown escapes imported
markup. JSON retains nested references, original metadata, all held/rejected items, edits, decisions
and review events. JSON is an audit export, including items excluded from readable release notes.

Draft reports carry explicit status, unresolved questions, diagnostics and limitations. Held/rejected
claims remain outside release-note sections. Approved-only reports include only explicitly approved,
supported statements; stale snapshots or no approved statements block that mode. Original generation
settings, model digest, source snapshots and validator versions remain available. Approval is a human
editorial decision, not independent confirmation of deployment or factual truth. Availability/category
warnings and possible duplicates require human judgment; no automatic merging or rewriting occurs.

Imports and editorial decisions remain in session memory. New imports reset them; a new generation
starts new pending editorial items. Save exports before closing the session. Report export does not
persist or restore app sessions. Documentation impact and update proposals are not implemented by
this change and are not invented or exported as completed work.
