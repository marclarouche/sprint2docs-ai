"""Local inspection UI; all parsing and normalization belongs to sprint2docs."""

import logging
from pathlib import Path

import streamlit as st

from report_ui import render_editorial_exports
from sprint2docs import ImportInput, import_batch
from sprint2docs.ai_writer import generate_release, snapshot
from sprint2docs.analysis import AUDIENCES, CATEGORIES, analyze, review_finding
from sprint2docs.config import load_limits
from sprint2docs.generation_models import GenerationSettings
from sprint2docs.ollama_adapter import OllamaAdapter, OllamaError

logger = logging.getLogger("sprint2docs.ui")
ROOT = Path(__file__).parent
st.set_page_config(page_title="Sprint2Docs AI", layout="wide")
st.title("Sprint2Docs AI — Milestone 3")
st.caption(
    "Local import and reviewable change analysis. Classifications are suggestions; availability requires verification."
)


def clear_result():
    st.session_state.pop("import_result", None)
    st.session_state.pop("analysis_result", None)
    st.session_state.pop("generated_release", None)
    st.session_state.pop("generation_error", None)
    for key in list(st.session_state):
        if key.startswith(("analysis_", "editorial_", "report_")):
            del st.session_state[key]


def save_review(index):
    analysis = st.session_state.analysis_result
    finding = analysis.findings[index]
    note = st.session_state.get(f"analysis_note_{index}", "")
    if not note.strip():
        st.session_state.analysis_error = "Enter a review note before saving."
        return
    reviewed = review_finding(
        finding,
        st.session_state[f"analysis_category_{index}"],
        st.session_state[f"analysis_audience_{index}"],
        st.session_state[f"analysis_status_{index}"],
        note,
    )
    findings = list(analysis.findings)
    findings[index] = reviewed
    st.session_state.analysis_result = analysis.model_copy(update={"findings": tuple(findings)})
    st.session_state.pop("analysis_error", None)
    st.session_state.analysis_saved_message = "Analysis review saved."


def do_import(use_samples):
    clear_result()
    try:
        limits = load_limits(ROOT / "config/import_limits.yaml")
        if use_samples:
            folder = ROOT / "samples/fleetops_demo"
            names = [
                "tickets.csv",
                "tickets.json",
                "pull_requests.json",
                "CHANGELOG.md",
                "documentation_inventory.json",
            ]
            files = [
                ImportInput(filename=name, data=(folder / name).read_bytes()) for name in names
            ]
        else:
            files = [
                ImportInput(filename=u.name, data=u.getvalue())
                for u in st.session_state.get("uploads", [])
            ]
        st.session_state.import_result = import_batch(files, limits)
    except Exception as error:
        logger.error("Import failed: subsystem=inspection category=%s", type(error).__name__)
        st.error("Unable to inspect imports. Check file schemas and resource limits.")


uploads = st.file_uploader(
    "Upload ticket CSV, ticket/PR/inventory JSON, or changelog Markdown",
    type=["csv", "json", "md"],
    accept_multiple_files=True,
    on_change=clear_result,
    key="uploads",
)
st.button("Load fictional FleetOps 2.4.0 demo", on_click=do_import, args=(True,))
st.button("Inspect imports", disabled=not uploads, on_click=do_import, args=(False,))
result = st.session_state.get("import_result")
if result is not None:
    columns = st.columns(5)
    for column, label, value in zip(
        columns,
        ["Artifacts", "Changes", "Inventory", "Warnings", "Errors"],
        [
            len(result.artifacts),
            len(result.changes),
            len(result.inventory),
            result.warning_count,
            result.error_count,
        ],
        strict=True,
    ):
        column.metric(label, value)
    if result.error_count:
        st.error(
            "Some input could not be imported. Review the validation summary. Only accepted records are shown."
        )
    st.caption(
        "Missing source fields remain unknown. Analysis preserves individual records and source identifiers."
    )
    with st.expander("Validation summary", expanded=bool(result.issues)):
        if result.issues:
            st.dataframe([i.model_dump() for i in result.issues], hide_index=True, width="stretch")
        else:
            st.success("All records passed structural validation.")
    for label, values in [
        ("Imported artifacts", result.artifacts),
        ("Normalized changes", result.changes),
        ("Documentation inventory", result.inventory),
        ("File provenance and metadata", result.files),
    ]:
        with st.expander(label):
            st.json([v.model_dump(mode="json") for v in values])
    st.caption(
        "Imported commands, URLs, HTML, and instructions are displayed as data. Source records stay in session memory; no files are written by inspection."
    )

    if "analysis_result" not in st.session_state:
        st.session_state.analysis_result = analyze(result)
    analysis = st.session_state.analysis_result
    st.subheader("Change analysis")
    st.caption(
        "Deterministic suggestions require review. Evidence does not prove deployment. No records are merged."
    )
    st.dataframe([f.model_dump(mode="json") for f in analysis.findings], hide_index=True)
    with st.expander("Associations and duplicate candidates"):
        st.json([r.model_dump(mode="json") for r in analysis.relationships])
        st.json([r.model_dump(mode="json") for r in analysis.unresolved_references])
        if analysis.relationships:
            link_index = st.selectbox(
                "Relationship to review", range(len(analysis.relationships)), key="analysis_link"
            )
            link_status = st.selectbox(
                "Relationship decision",
                ["pending", "approved", "rejected", "needs_clarification"],
                key="analysis_link_status",
            )
            if st.button("Save relationship decision"):
                links = list(analysis.relationships)
                links[link_index] = links[link_index].model_copy(
                    update={"review_status": link_status}
                )
                st.session_state.analysis_result = analysis.model_copy(
                    update={"relationships": tuple(links)}
                )
                st.success("Decision saved. The analysis table refreshes on your next interaction.")
    if analysis.findings:
        statuses = ["pending", "approved", "rejected", "needs_clarification"]
        status_labels = {
            "pending": "Pending",
            "approved": "Approved",
            "rejected": "Rejected",
            "needs_clarification": "Needs clarification",
        }
        pending_count = sum(f.review_status == "pending" for f in analysis.findings)
        st.caption(f"{pending_count} of {len(analysis.findings)} changes awaiting review.")
        show_saved = st.checkbox("Show saved reviews", key="analysis_show_saved")
        review_indices = [
            i for i, f in enumerate(analysis.findings) if show_saved or f.review_status == "pending"
        ]
        if st.session_state.get("analysis_saved_message"):
            st.success(st.session_state.analysis_saved_message)
        if not review_indices:
            st.info(
                "No pending changes. Turn on Show saved reviews to inspect or revise saved decisions."
            )
        else:
            if st.session_state.get("analysis_selection") not in review_indices:
                st.session_state.analysis_selection = review_indices[0]
            index = st.selectbox(
                "Change to review",
                review_indices,
                format_func=lambda i: (
                    f"{i + 1}. {result.artifacts[i].artifact_id} — {result.artifacts[i].title} "
                    f"[{status_labels[analysis.findings[i].review_status]}] "
                    f"({result.artifacts[i].provenance.filename}, record "
                    f"{result.artifacts[i].provenance.record_number})"
                ),
                key="analysis_selection",
            )
            finding = analysis.findings[index]
            with st.container():
                st.selectbox(
                    "Category",
                    CATEGORIES,
                    index=CATEGORIES.index(finding.category),
                    key=f"analysis_category_{index}",
                )
                st.selectbox(
                    "Audience",
                    AUDIENCES,
                    index=AUDIENCES.index(finding.audience),
                    key=f"analysis_audience_{index}",
                )
                st.selectbox(
                    "Review decision",
                    statuses,
                    index=statuses.index(finding.review_status),
                    key=f"analysis_status_{index}",
                )
                st.text_input(
                    "Review note", value=finding.reviewer_note or "", key=f"analysis_note_{index}"
                )
                st.button(
                    "Save analysis review", key="save_analysis", on_click=save_review, args=(index,)
                )
                if st.session_state.get("analysis_error"):
                    st.error(st.session_state.analysis_error)

    st.subheader("Release note drafts")
    st.caption(
        "Generate locally with Ollama. All output remains a draft requiring editorial verification."
    )
    if st.button("Find local Ollama models"):
        try:
            st.session_state.ollama_models = OllamaAdapter().models()
            st.session_state.pop("generation_error", None)
        except OllamaError as error:
            st.session_state.generation_error = str(error)
    available_models = st.session_state.get("ollama_models", {})
    if available_models:
        model = st.selectbox("Local model", tuple(available_models))
        releases = sorted({a.release_id for a in result.artifacts if a.release_id})
        release = st.selectbox("Draft release", releases) if releases else None
        timeout = st.number_input(
            "Request timeout (seconds)", min_value=1, max_value=300, value=120
        )
        with st.expander("Generation size"):
            batch_size = st.number_input("Records per batch", min_value=1, max_value=8, value=4)
            output_tokens = st.number_input(
                "Maximum output tokens per batch", min_value=128, max_value=8000, value=3000
            )
            st.caption(
                "Smaller batches can help slower models. Too few output tokens may truncate a response."
            )
        if st.button("Generate release note drafts", disabled=release is None):
            try:
                batch_progress = st.empty()

                def show_batch(current, total):
                    batch_progress.info(f"Drafting batch {current} of {total} with local Ollama…")

                with st.spinner("Drafting from imported sources with local Ollama…"):
                    generated = generate_release(
                        result,
                        st.session_state.analysis_result,
                        release,
                        GenerationSettings(
                            model=model,
                            timeout_seconds=int(timeout),
                            batch_records=int(batch_size),
                            num_predict=int(output_tokens),
                        ),
                        OllamaAdapter(),
                        progress=show_batch,
                    )
                batch_progress.empty()
                if generated.status != "failed":
                    st.session_state.generated_release = generated
                    st.session_state.pop("generation_error", None)
                else:
                    st.session_state.generation_error = (
                        "Generation failed. Previous drafts and imports remain available. "
                        + " ".join(generated.diagnostics)
                    )
            except (ValueError, OllamaError) as error:
                st.session_state.generation_error = str(error)
    else:
        st.info("Find your installed models to enable drafting. Start Ollama if it is unavailable.")
    if st.session_state.get("generation_error"):
        st.error(st.session_state.generation_error)
    generated = st.session_state.get("generated_release")
    if generated is not None:
        stale = generated.source_snapshot_sha256 != snapshot(
            result
        ) or generated.analysis_snapshot_sha256 != snapshot(st.session_state.analysis_result)
        if stale:
            st.warning(
                "Imports or analysis have changed. Generate a new draft before using this output."
            )
        st.text(
            f"DRAFT — release {generated.release_id}; status: {generated.status}; model: {generated.settings.model}"
        )
        for audience, label in [
            ("customer", "Customer release notes (original model draft)"),
            ("technical", "Technical release notes (original model draft)"),
        ]:
            st.write(label)
            notes = [
                c
                for c in generated.claims
                if c.claim.audience == audience and c.status != "unsupported"
            ]
            if not notes:
                st.info("No validated draft statements were produced for this audience.")
            for item in notes:
                st.text(f"[{item.claim.category}] {item.claim.text}")
                st.caption(
                    "Pending review — source references do not verify the claim or deployment."
                )
                with st.expander("Supporting source excerpts"):
                    st.json([e.model_dump(mode="json") for e in item.claim.evidence])
                    st.json([p.model_dump(mode="json") for p in item.provenance])
        with st.expander("Claims held for clarification"):
            st.json(
                [c.model_dump(mode="json") for c in generated.claims if c.status == "unsupported"]
            )
        with st.expander("Engineering clarification questions", expanded=True):
            for question in generated.questions:
                st.text(question.question.question)
                st.json([e.model_dump(mode="json") for e in question.question.evidence])
        with st.expander("Generation details and limitations"):
            st.json(generated.model_dump(mode="json", exclude={"claims", "questions"}))

        render_editorial_exports(result, st.session_state.analysis_result, generated)
