"""Streamlit editorial controls and local report downloads."""

import streamlit as st

from sprint2docs.analysis import CATEGORIES
from sprint2docs.exporters import (
    build_report,
    export_html,
    export_json,
    export_markdown,
    export_package,
)
from sprint2docs.generation_models import DraftClaim
from sprint2docs.review import (
    answer_question,
    decide_item,
    duplicate_candidates,
    generation_key,
    is_stale,
    item_warnings,
    revise_item,
    start_review,
)


def _candidate(item, pool):
    prefix = f"editorial_{item.item_id}"
    text = st.session_state[prefix + "_text"]
    selected = st.session_state[prefix + "_evidence"]
    if not text.strip() or not 1 <= len(selected) <= 3:
        raise ValueError("Enter wording and select one to three supporting excerpts.")
    return DraftClaim(
        text=text,
        category=st.session_state[prefix + "_category"],
        audience=st.session_state[prefix + "_audience"],
        evidence=tuple(pool[i] for i in selected),
    )


def _save_wording(item_id, pool, imported, analysis):
    try:
        review = st.session_state.editorial_review
        item = next(i for i in review.items if i.item_id == item_id)
        revised = revise_item(
            review,
            item_id,
            _candidate(item, pool),
            imported,
            analysis,
            st.session_state.editorial_reviewer,
        )
        st.session_state.editorial_review = revised
        if revised != review:
            prefix = f"editorial_{item_id}"
            st.session_state[prefix + "_decision"] = "pending"
            st.session_state[prefix + "_verified"] = False
            st.session_state[prefix + "_note"] = ""
            st.session_state.editorial_message = (
                f"{item_id}: wording/evidence saved; approval reset to Pending."
            )
        else:
            st.session_state.editorial_message = f"{item_id}: no changes to saved wording."
        st.session_state.pop("editorial_error", None)
    except ValueError as error:
        st.session_state.editorial_error = str(error)


def _save_decision(item_id, pool, imported, analysis, generated):
    try:
        review = st.session_state.editorial_review
        item = next(i for i in review.items if i.item_id == item_id)
        revised = revise_item(
            review,
            item_id,
            _candidate(item, pool),
            imported,
            analysis,
            st.session_state.editorial_reviewer,
        )
        if revised != review:
            _save_wording(item_id, pool, imported, analysis)
            st.session_state.editorial_message = (
                "Changes saved as Pending. Inspect the revised evidence, then record your decision."
            )
            return
        prefix = f"editorial_{item_id}"
        st.session_state.editorial_review = decide_item(
            review,
            item_id,
            st.session_state[prefix + "_decision"],
            st.session_state.editorial_reviewer,
            st.session_state[prefix + "_note"],
            generated,
            imported,
            analysis,
            evidence_verified=st.session_state[prefix + "_verified"],
        )
        st.session_state.editorial_message = f"{item_id}: editorial decision saved."
        st.session_state.pop("editorial_error", None)
    except ValueError as error:
        st.session_state.editorial_error = str(error)


def _save_answer(question_id):
    try:
        prefix = f"editorial_{question_id}"
        st.session_state.editorial_review = answer_question(
            st.session_state.editorial_review,
            question_id,
            st.session_state[prefix + "_answer"],
            st.session_state.editorial_reviewer,
            st.session_state[prefix + "_resolved"],
        )
        st.session_state.editorial_message = f"{question_id}: answer saved with human attribution."
        st.session_state.pop("editorial_error", None)
    except ValueError as error:
        st.session_state.editorial_error = str(error)


def render_editorial_exports(imported, analysis, generated):
    key = generation_key(generated)
    existing = st.session_state.get("editorial_review")
    if existing is None or existing.generation_key != key:
        for state_key in list(st.session_state):
            if state_key.startswith("editorial_"):
                del st.session_state[state_key]
        st.session_state.editorial_review = start_review(generated)
    review = st.session_state.editorial_review
    st.subheader("Editorial review and reports")
    st.caption(
        "Analysis approvals do not approve AI wording. Edit statements, reject duplicates, and explicitly verify evidence before approving a draft statement."
    )
    st.text_input("Reviewer name", value="Local reviewer", key="editorial_reviewer", max_chars=200)
    if is_stale(generated, imported, analysis):
        st.warning(
            "This generation is stale. Draft/audit exports are available; regenerate before editorial approval or approved-only export."
        )
    if st.session_state.get("editorial_message"):
        st.success(st.session_state.editorial_message)
    if st.session_state.get("editorial_error"):
        st.error(st.session_state.editorial_error)
    counts = [
        sum(i.review_status == status for i in review.items)
        for status in ("pending", "approved", "rejected", "needs_clarification")
    ]
    counts.append(sum(i.current.status == "unsupported" for i in review.items))
    for column, label, count in zip(
        st.columns(5),
        [
            "Drafts pending",
            "Drafts approved",
            "Drafts rejected",
            "Need clarification",
            "Evidence held",
        ],
        counts,
        strict=True,
    ):
        column.metric(label, count)
    candidates = duplicate_candidates(review, analysis)
    with st.expander("Potential duplicate draft statements", expanded=bool(candidates)):
        if not candidates:
            st.info("No active duplicate candidates found.")
        by_id = {i.item_id: i for i in review.items}
        for pair in candidates:
            st.text(f"{pair.left_id} / {pair.right_id}: {pair.reason}")
            st.text(by_id[pair.left_id].current.claim.text)
            st.text(by_id[pair.right_id].current.claim.text)
        st.caption(
            "To remove a duplicate from release notes, reject that statement and note the retained NOTE ID. Source records remain intact."
        )
    if review.items:
        pool = []
        for item in review.items:
            for evidence in item.current.claim.evidence:
                if evidence not in pool:
                    pool.append(evidence)
        for claim in generated.claims:
            for evidence in claim.claim.evidence:
                if evidence not in pool:
                    pool.append(evidence)
        item_ids = [i.item_id for i in review.items]
        selected_id = st.selectbox(
            "Generated statement to review",
            item_ids,
            format_func=lambda note_id: (
                f"{note_id} — {next(i for i in review.items if i.item_id == note_id).review_status.replace('_', ' ')}"
            ),
            key="editorial_selection",
        )
        item = next(i for i in review.items if i.item_id == selected_id)
        for warning in item_warnings(item, analysis):
            st.warning(warning)
        if item.current.issues:
            st.warning("Evidence issues: " + ", ".join(item.current.issues))
        with st.expander("Evidence for selected statement", expanded=True):
            for evidence in item.current.claim.evidence:
                st.text(f"{evidence.artifact_id} — {evidence.field}: {evidence.excerpt}")
            st.json([p.model_dump(mode="json") for p in item.current.provenance])
        prefix = f"editorial_{item.item_id}"
        source_by_key = {s.artifact_key: s for s in imported.artifacts}

        def evidence_label(index):
            evidence = pool[index]
            source = source_by_key.get(evidence.artifact_key)
            location = (
                f"{source.provenance.filename}, record {source.provenance.record_number}"
                if source
                else "unresolved source"
            )
            return f"{index + 1}. {evidence.artifact_id} ({location}) — {evidence.field}: {evidence.excerpt[:90]}"

        with st.form(f"editorial_form_{item.item_id}"):
            st.text_area(
                "Draft wording", value=item.current.claim.text, max_chars=500, key=prefix + "_text"
            )
            st.selectbox(
                "Draft category",
                CATEGORIES,
                index=CATEGORIES.index(item.current.claim.category),
                key=prefix + "_category",
            )
            st.selectbox(
                "Draft audience",
                ["customer", "technical"],
                index=["customer", "technical"].index(item.current.claim.audience),
                key=prefix + "_audience",
            )
            st.multiselect(
                "Supporting excerpts (choose one to three)",
                range(len(pool)),
                default=[i for i, e in enumerate(pool) if e in item.current.claim.evidence],
                format_func=evidence_label,
                key=prefix + "_evidence",
            )
            st.form_submit_button(
                "Save wording changes",
                on_click=_save_wording,
                args=(item.item_id, pool, imported, analysis),
            )
            statuses = ["pending", "approved", "rejected", "needs_clarification"]
            st.selectbox(
                "Editorial decision",
                statuses,
                index=statuses.index(item.review_status),
                key=prefix + "_decision",
            )
            st.text_area(
                "Editorial decision note",
                value=item.review_note or "",
                max_chars=2000,
                key=prefix + "_note",
            )
            st.checkbox(
                "I checked the statement against its evidence, including any availability or deployment claims.",
                key=prefix + "_verified",
            )
            st.form_submit_button(
                "Save editorial decision",
                on_click=_save_decision,
                args=(item.item_id, pool, imported, analysis, generated),
            )
        st.caption(
            "Wording, category, audience or evidence changes reset approval to Pending. Resolve evidence issues before approval. Approval is an editorial decision, not independent verification of software behavior."
        )
    if review.questions:
        with st.expander("Answer engineering clarification questions"):
            question_ids = [q.question_id for q in review.questions]
            selected_question = st.selectbox("Question", question_ids, key="editorial_question")
            q = next(q for q in review.questions if q.question_id == selected_question)
            original = generated.questions[q.source_question_index].question
            st.text(original.question)
            for evidence in original.evidence:
                st.text(f"{evidence.artifact_id}: {evidence.excerpt}")
            with st.form(f"editorial_question_form_{q.question_id}"):
                st.text_area(
                    "Human answer (separate from imported evidence)",
                    value=q.answer or "",
                    max_chars=4000,
                    key=f"editorial_{q.question_id}_answer",
                )
                st.checkbox(
                    "Resolved",
                    value=q.status == "resolved",
                    key=f"editorial_{q.question_id}_resolved",
                )
                st.form_submit_button(
                    "Save clarification answer", on_click=_save_answer, args=(q.question_id,)
                )
    st.subheader("Download reports")
    st.text_input("Product name for reports", value="Product", max_chars=200, key="report_product")
    mode = st.radio(
        "Report contents",
        ["draft", "approved_only"],
        format_func=lambda value: (
            "Draft report (includes pending items)"
            if value == "draft"
            else "Approved statements only"
        ),
        key="report_mode",
    )
    try:
        report = build_report(
            st.session_state.report_product, imported, analysis, generated, review, mode
        )
    except ValueError as error:
        st.info(str(error))
        return
    st.caption(
        "Markdown and HTML follow the selected report mode. JSON includes all original sources, held/rejected claims, edits and review decisions for traceability. Downloads are created locally in memory."
    )
    st.download_button(
        "Download complete report package (ZIP)",
        export_package(report),
        "release-report-package.zip",
        mime="application/zip",
        on_click="ignore",
    )
    left, right = st.columns(2)
    with left:
        st.download_button(
            "Download full report (Markdown)",
            export_markdown(report),
            "release-report.md",
            mime="text/markdown",
            on_click="ignore",
        )
        st.download_button(
            "Download customer release notes",
            export_markdown(report, "customer"),
            "customer-release-notes.md",
            mime="text/markdown",
            on_click="ignore",
        )
        st.download_button(
            "Download technical release notes",
            export_markdown(report, "technical"),
            "technical-release-notes.md",
            mime="text/markdown",
            on_click="ignore",
        )
    with right:
        st.download_button(
            "Download complete analysis (JSON)",
            export_json(report),
            "complete-analysis.json",
            mime="application/json",
            on_click="ignore",
        )
        st.download_button(
            "Download traceability (JSON)",
            export_json(report, trace_only=True),
            "traceability.json",
            mime="application/json",
            on_click="ignore",
        )
        st.download_button(
            "Download print-friendly report (HTML)",
            export_html(report),
            "print-report.html",
            mime="text/html",
            on_click="ignore",
        )
    st.caption(
        "To print or save a PDF: download the HTML report, open it in your browser, then press Command+P on Mac (Control+P on Windows/Linux). No external assets or scripts are used."
    )
    with st.expander("Readable report preview"):
        st.markdown(export_markdown(report).decode("utf-8"), unsafe_allow_html=False)
