"""Pure in-memory report builders. No filesystem, network, or publishing side effects."""

import html
import json
import re
from datetime import UTC, datetime
from io import BytesIO
from typing import Any, Literal
from zipfile import ZIP_DEFLATED, ZipFile

from .analysis import AnalysisResult
from .generation_models import GenerationResult
from .models import ImportResult, Model
from .review import EditorialReview, check_review, duplicate_candidates, is_stale, item_warnings

ExportMode = Literal["draft", "approved_only"]
AudienceFilter = Literal["all", "customer", "technical"]


class ReportBlock(Model):
    kind: Literal["heading", "text", "quote"]
    text: str
    level: int = 2


class ReleaseReport(Model):
    product: str
    json_scope: Literal["complete_audit_including_excluded_items"] = (
        "complete_audit_including_excluded_items"
    )
    exported_at: str
    mode: ExportMode
    stale: bool
    imports: ImportResult
    analysis: AnalysisResult
    generation: GenerationResult
    editorial: EditorialReview
    limitations: tuple[str, ...] = (
        "Source references establish provenance, not factual truth or deployed functionality.",
        "Editorial approval is a human decision; it does not independently verify software behavior.",
        "Potential duplicates are suggestions; source records and note wording are never silently merged.",
        "Documentation impact and update proposals have not been generated in this workflow.",
    )


def build_report(
    product: str,
    imported: ImportResult,
    analysis: AnalysisResult,
    generated: GenerationResult,
    editorial: EditorialReview,
    mode: ExportMode = "draft",
) -> ReleaseReport:
    if not product.strip() or len(product) > 200:
        raise ValueError("Enter a product name of 1–200 characters.")
    if mode not in ("draft", "approved_only"):
        raise ValueError("Unknown export mode.")
    check_review(editorial, generated)
    stale = is_stale(generated, imported, analysis)
    if mode == "approved_only":
        if stale or generated.status == "failed":
            raise ValueError(
                "Approved-only export requires current, successful generation sources and analysis."
            )
        if not any(
            i.review_status == "approved" and i.current.status != "unsupported"
            for i in editorial.items
        ):
            raise ValueError(
                "Approve at least one generated statement before approved-only export."
            )
    return ReleaseReport(
        product=product.strip(),
        exported_at=datetime.now(UTC).isoformat(),
        mode=mode,
        stale=stale,
        imports=imported,
        analysis=analysis,
        generation=generated,
        editorial=editorial,
    )


def report_blocks(
    report: ReleaseReport, audience: AudienceFilter = "all"
) -> tuple[ReportBlock, ...]:
    if audience not in ("all", "customer", "technical"):
        raise ValueError("Unknown report audience.")
    blocks: list[ReportBlock] = []

    def heading(text: str, level: int = 2) -> None:
        blocks.append(ReportBlock(kind="heading", text=text, level=level))

    def text(value: str) -> None:
        blocks.append(ReportBlock(kind="text", text=value))

    def quote(value: str) -> None:
        blocks.append(ReportBlock(kind="quote", text=value))

    gen = report.generation
    heading(f"{report.product} — Release {gen.release_id}", 1)
    text(
        "DRAFT — not approved for publication"
        if report.mode == "draft"
        else "EDITORIALLY APPROVED STATEMENTS ONLY"
    )
    text(f"Exported: {report.exported_at} | Generated: {gen.created_at}")
    text(
        f"Tool: {gen.tool_version} | Model: {gen.settings.model} | Model digest: {gen.model_digest}"
    )
    text(
        f"Generation status: {gen.status} | Prompt: {gen.prompt_version} | Original validator: {gen.validator_version} | Editorial validator: {report.editorial.validator_version}"
    )
    text(
        f"Settings: temperature {gen.settings.temperature}; seed {gen.settings.seed}; output tokens {gen.settings.num_predict}; context tokens {gen.settings.num_ctx}; batch records {gen.settings.batch_records}; timeout {gen.settings.timeout_seconds}s."
    )
    if report.stale:
        text(
            "STALE DRAFT: imports or analysis changed after generation. Regenerate before approval or publication."
        )
    text(
        "Analysis review decisions do not approve generated wording. Every statement below carries its own editorial status."
    )
    counts = {
        status: sum(i.review_status == status for i in report.editorial.items)
        for status in ("pending", "approved", "rejected", "needs_clarification")
    }
    text("Editorial counts: " + "; ".join(f"{k}: {v}" for k, v in counts.items()))
    for target, label in (
        ("customer", "Customer release notes"),
        ("technical", "Technical release notes"),
    ):
        if audience != "all" and audience != target:
            continue
        heading(label)
        items = [
            i
            for i in report.editorial.items
            if i.current.claim.audience == target
            and i.current.status != "unsupported"
            and i.review_status != "rejected"
            and (report.mode == "draft" or i.review_status == "approved")
        ]
        if not items:
            text("No eligible statements for this audience.")
        for item in items:
            claim = item.current.claim
            heading(
                f"{item.item_id} — {claim.category} — {item.review_status.replace('_', ' ').title()}",
                3,
            )
            text(claim.text)
            if item.review_note:
                text(
                    f"Reviewer: {item.reviewer}; reviewed: {item.reviewed_at}. Decision note: {item.review_note}"
                )
            for warning in item_warnings(item, report.analysis):
                text("Review attention: " + warning)
            for evidence in claim.evidence:
                quote(f"Source {evidence.artifact_id} | {evidence.field}: {evidence.excerpt}")
            for p in item.current.provenance:
                text(
                    f"Provenance: {p.filename}, record {p.record_number}, lines {p.line_start}–{p.line_end}"
                )
    heading("Engineering clarification questions")
    if not report.editorial.questions:
        text("No validated clarification questions were generated.")
    for q in report.editorial.questions:
        original = gen.questions[q.source_question_index].question
        heading(f"{q.question_id} — {q.status.title()}", 3)
        text(original.question)
        for evidence in original.evidence:
            quote(f"Source {evidence.artifact_id} | {evidence.field}: {evidence.excerpt}")
        if q.answer:
            text(f"Human-entered answer (separate from imported evidence): {q.answer}")
            text(f"Attributed to: {q.answered_by}; recorded: {q.answered_at}")
    heading("Potential duplicate statements")
    candidates = duplicate_candidates(report.editorial, report.analysis)
    if not candidates:
        text("No active duplicate candidates identified by the current rules.")
    for candidate in candidates:
        text(f"{candidate.left_id} / {candidate.right_id}: {candidate.reason}")
    if report.mode == "draft":
        heading("Held and rejected statements — excluded from release notes")
        for item in report.editorial.items:
            if item.current.status == "unsupported" or item.review_status == "rejected":
                text(f"{item.item_id}: {item.current.claim.text}")
                text(
                    f"Validation: {item.current.status}; issues: {', '.join(item.current.issues) or 'none'}; editorial decision: {item.review_status}; note: {item.review_note or 'none'}"
                )
                for evidence in item.current.claim.evidence:
                    quote(
                        f"Claimed source {evidence.artifact_id} | {evidence.field}: {evidence.excerpt}"
                    )
    heading("Processing diagnostics and limitations")
    for diagnostic in gen.diagnostics:
        text("Original generation diagnostic: " + diagnostic)
    text(
        f"Import errors: {report.imports.error_count}; import warnings: {report.imports.warning_count}."
    )
    for limitation in report.limitations:
        text(limitation)
    text(f"Source snapshot SHA-256: {gen.source_snapshot_sha256}")
    text(f"Analysis snapshot SHA-256: {gen.analysis_snapshot_sha256}")
    return tuple(blocks)


def markdown_text(value: str) -> str:
    # Escape source/model text so it cannot create HTML, images, headings or links.
    escaped = html.escape(value, quote=False)
    return re.sub(r"([\\`*_{}\[\]()#!|+\-.])", r"\\\1", escaped)


def export_markdown(report: ReleaseReport, audience: AudienceFilter = "all") -> bytes:
    lines: list[str] = []
    for block in report_blocks(report, audience):
        value = markdown_text(block.text)
        if block.kind == "heading":
            lines.append("#" * block.level + " " + value)
        elif block.kind == "quote":
            lines.append("\n".join("> " + line for line in value.splitlines()))
        else:
            lines.append("\n".join(value.splitlines()))
    return ("\n\n".join(lines) + "\n").encode("utf-8")


def traceability(report: ReleaseReport) -> dict[str, Any]:
    return {
        "schema_version": "1.0",
        "json_scope": "traceability_audit_including_excluded_items",
        "product": report.product,
        "release_id": report.generation.release_id,
        "exported_at": report.exported_at,
        "mode": report.mode,
        "stale": report.stale,
        "tool_version": report.generation.tool_version,
        "model": report.generation.settings.model,
        "model_digest": report.generation.model_digest,
        "settings": report.generation.settings.model_dump(mode="json"),
        "generation_key": report.editorial.generation_key,
        "original_validator": report.generation.validator_version,
        "editorial_validator": report.editorial.validator_version,
        "source_snapshot_sha256": report.generation.source_snapshot_sha256,
        "analysis_snapshot_sha256": report.generation.analysis_snapshot_sha256,
        "items": [item.model_dump(mode="json") for item in report.editorial.items],
        "questions": [q.model_dump(mode="json") for q in report.editorial.questions],
        "original_questions": [q.model_dump(mode="json") for q in report.generation.questions],
        "duplicate_candidates": [
            d.model_dump(mode="json")
            for d in duplicate_candidates(report.editorial, report.analysis)
        ],
        "events": [e.model_dump(mode="json") for e in report.editorial.events],
        "diagnostics": list(report.generation.diagnostics),
        "limitations": list(report.limitations),
    }


def export_json(report: ReleaseReport, trace_only: bool = False) -> bytes:
    value = traceability(report) if trace_only else report.model_dump(mode="json")
    return json.dumps(value, ensure_ascii=False, allow_nan=False, indent=2).encode("utf-8")


def export_html(report: ReleaseReport, audience: AudienceFilter = "all") -> bytes:
    parts = []
    for block in report_blocks(report, audience):
        tag = (
            f"h{block.level}"
            if block.kind == "heading"
            else "blockquote"
            if block.kind == "quote"
            else "p"
        )
        parts.append(f"<{tag}>{html.escape(block.text)}</{tag}>")
    title = html.escape(f"{report.product} — Release {report.generation.release_id}")
    document = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'">
<title>{title}</title><style>
body {{ font: 15px/1.55 system-ui, sans-serif; color: #172336; background: white; max-width: 900px; margin: 36px auto; padding: 0 24px; }}
h1 {{ font-size: 27px; }} h2 {{ font-size: 21px; border-bottom: 1px solid #cbd5e1; padding-bottom: 6px; margin-top: 30px; }}
h3 {{ font-size: 16px; }} p, blockquote {{ white-space: pre-wrap; overflow-wrap: anywhere; }}
blockquote {{ border-left: 3px solid #94a3b8; padding-left: 14px; margin-left: 0; color: #334155; font-size: 13px; }}
@page {{ margin: 16mm; }} @media print {{ body {{ margin: 0; padding: 0; font-size: 11pt; max-width: none; }} h1,h2,h3 {{ break-after: avoid; }} blockquote {{ break-inside: avoid; }} }}
</style></head><body><main>{"".join(parts)}</main></body></html>"""
    return document.encode("utf-8")


def export_package(report: ReleaseReport) -> bytes:
    """Fixed filenames only; imported paths never determine archive entries."""
    buffer = BytesIO()
    with ZipFile(buffer, "w", ZIP_DEFLATED) as archive:
        archive.writestr("release-report.md", export_markdown(report))
        archive.writestr("customer-release-notes.md", export_markdown(report, "customer"))
        archive.writestr("technical-release-notes.md", export_markdown(report, "technical"))
        archive.writestr("complete-analysis.json", export_json(report))
        archive.writestr("traceability.json", export_json(report, trace_only=True))
        archive.writestr("print-report.html", export_html(report))
        archive.writestr(
            "README.txt",
            "Open print-report.html in your browser and use Print / Save as PDF.\n"
            "Markdown and HTML follow the selected draft/approved-only mode.\n"
            "JSON is a complete audit record, including rejected/held items and source contents.\n"
            "Human-entered answers are separate from imported evidence.\n",
        )
    return buffer.getvalue()
