"""Editorial approval, evidence integrity, export fidelity and inert rendering."""

import json
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from zipfile import ZipFile

import pytest

from sprint2docs import ImportInput, import_batch
from sprint2docs.ai_writer import snapshot
from sprint2docs.analysis import AnalysisResult, analyze
from sprint2docs.claim_validator import validate_claim
from sprint2docs.exporters import (
    ReleaseReport,
    build_report,
    export_html,
    export_json,
    export_markdown,
    export_package,
)
from sprint2docs.generation_models import (
    Clarification,
    DraftClaim,
    Evidence,
    GenerationResult,
    GenerationSettings,
    ValidatedQuestion,
)
from sprint2docs.models import ImportResult
from sprint2docs.review import (
    EditorialReview,
    answer_question,
    decide_item,
    duplicate_candidates,
    is_stale,
    item_warnings,
    revise_item,
    start_review,
)


@dataclass
class Case:
    imported: ImportResult
    analysis: AnalysisResult
    generation: GenerationResult
    review: EditorialReview


@pytest.fixture
def case():
    description = (
        "Adds administrator TOTP enrollment. Deployment and mandatory enforcement are unconfirmed."
    )
    data = json.dumps(
        {
            "schema_version": "1.0",
            "artifact_type": "ticket",
            "records": [
                {
                    "id": "FLEET-142",
                    "title": "Administrator enrollment",
                    "description": description,
                    "release_id": "2.4.0",
                    "change_type": "new_feature",
                    "labels": ["administrator-facing"],
                    "custom": {"nested": ["preserved"]},
                }
            ],
        }
    ).encode()
    imported = import_batch(
        [
            ImportInput(filename="tickets.json", data=data),
            ImportInput(
                filename="tickets-copy.json",
                data=json.dumps({**json.loads(data), "export_name": "second copy"}).encode(),
            ),
        ]
    )
    analysis = analyze(imported)
    analysis = analysis.model_copy(
        update={
            "findings": tuple(
                f.model_copy(update={"review_status": "approved"}) for f in analysis.findings
            )
        }
    )

    def evidence(index):
        source = imported.artifacts[index]
        return Evidence(
            artifact_key=source.artifact_key,
            artifact_id=source.artifact_id,
            field="description",
            excerpt="Adds administrator TOTP enrollment.",
        )

    first = DraftClaim(
        audience="customer",
        category="New Feature",
        text="Adds administrator TOTP enrollment.",
        evidence=(evidence(0),),
    )
    second = DraftClaim(
        audience="customer",
        category="Enhancement",
        text="Administrators can now enroll in TOTP MFA.",
        evidence=(evidence(1),),
    )
    bad = DraftClaim(
        audience="technical",
        category="New Feature",
        text="Invented speed improvement of 900%.",
        evidence=(evidence(0),),
    )
    generation = GenerationResult(
        release_id="2.4.0",
        created_at="2026-10-14T22:00:00+00:00",
        settings=GenerationSettings(model="local:test"),
        model_digest="a" * 64,
        source_snapshot_sha256=snapshot(imported),
        analysis_snapshot_sha256=snapshot(analysis),
        source_keys=tuple(s.artifact_key for s in imported.artifacts),
        claims=tuple(validate_claim(c, imported.artifacts) for c in (first, second, bad)),
        questions=(
            ValidatedQuestion(
                question=Clarification(question="Has this been deployed?", evidence=(evidence(0),)),
                provenance=(imported.artifacts[0].provenance,),
            ),
        ),
        diagnostics=("Unsupported claims are held outside release note drafts.",),
        status="partial",
    )
    return Case(imported, analysis, generation, start_review(generation))


def decide(case, review, note_id="NOTE-001", status="approved", verified=True):
    return decide_item(
        review,
        note_id,
        status,
        "Alex",
        "Compared wording with source evidence.",
        case.generation,
        case.imported,
        case.analysis,
        evidence_verified=verified,
    )


def test_analysis_approval_never_auto_approves_generated_wording(case):
    assert all(f.review_status == "approved" for f in case.analysis.findings)
    assert all(i.review_status == "pending" for i in case.review.items)
    with pytest.raises(ValueError, match="Approve at least one"):
        build_report(
            "FleetOps", case.imported, case.analysis, case.generation, case.review, "approved_only"
        )


def test_approval_requires_confirmation_and_supported_evidence(case):
    with pytest.raises(ValueError, match="Explicitly confirm"):
        decide(case, case.review, verified=False)
    with pytest.raises(ValueError, match="Resolve evidence"):
        decide(case, case.review, "NOTE-003")
    with pytest.raises(ValueError, match="name and decision note"):
        decide_item(
            case.review,
            "NOTE-001",
            "approved",
            "",
            "",
            case.generation,
            case.imported,
            case.analysis,
            True,
        )
    approved = decide(case, case.review)
    assert approved.items[0].review_status == "approved"
    assert approved.items[0].reviewer == "Alex"
    assert approved.events[-1].action == "decision_approved"


@pytest.mark.parametrize("change", ["text", "category", "audience", "evidence"])
def test_material_edits_reset_approval_and_preserve_original(case, change):
    review = decide(case, case.review)
    original_json = case.generation.model_dump_json()
    claim = review.items[0].current.claim
    updates = {
        "text": "Adds an administrator enrollment workflow.",
        "category": "Enhancement",
        "audience": "technical",
        "evidence": case.review.items[1].current.claim.evidence,
    }
    revised = revise_item(
        review,
        "NOTE-001",
        claim.model_copy(update={change: updates[change]}),
        case.imported,
        case.analysis,
        "Alex",
    )
    assert revised.items[0].review_status == "pending"
    assert revised.items[0].reviewer is None and revised.items[0].reviewed_at is None
    assert revised.events[-1].action == "edited_approval_reset"
    assert case.generation.model_dump_json() == original_json


def test_unchanged_wording_does_not_reset_approval(case):
    review = decide(case, case.review)
    assert (
        revise_item(
            review, "NOTE-001", review.items[0].current.claim, case.imported, case.analysis, "Alex"
        )
        == review
    )


def test_duplicate_candidates_are_explicit_and_rejection_excludes_only_note(case):
    assert len(duplicate_candidates(case.review, case.analysis)) == 1
    review = decide(case, case.review, "NOTE-002", "rejected", False)
    assert not duplicate_candidates(review, case.analysis)
    report = build_report("FleetOps", case.imported, case.analysis, case.generation, review)
    text = export_markdown(report).decode()
    main = text.split("## Held and rejected")[0]
    assert "Administrators can now enroll" not in main
    assert "Administrators can now enroll" in text
    assert len(report.imports.artifacts) == 2


def test_category_and_availability_issues_are_visible(case):
    warnings = item_warnings(case.review.items[1], case.analysis)
    assert any("Category differs" in w for w in warnings)
    assert any("availability/deployment" in w for w in warnings)
    assert (
        "Review attention"
        in export_markdown(
            build_report("FleetOps", case.imported, case.analysis, case.generation, case.review)
        ).decode()
    )


def test_stale_generation_can_export_draft_but_not_approve_or_export_approved(case):
    changed = case.analysis.model_copy(
        update={
            "findings": (case.analysis.findings[0].model_copy(update={"audience": "Uncertain"}),)
            + case.analysis.findings[1:]
        }
    )
    assert is_stale(case.generation, case.imported, changed)
    with pytest.raises(ValueError, match="Regenerate"):
        decide_item(
            case.review,
            "NOTE-001",
            "approved",
            "Alex",
            "Checked",
            case.generation,
            case.imported,
            changed,
            True,
        )
    draft = build_report("FleetOps", case.imported, changed, case.generation, case.review)
    assert "STALE DRAFT" in export_markdown(draft).decode()
    with pytest.raises(ValueError, match="current"):
        build_report(
            "FleetOps",
            case.imported,
            changed,
            case.generation,
            decide(case, case.review),
            "approved_only",
        )


def test_approved_only_is_filtered_but_json_audit_is_complete(case):
    review = decide(case, case.review)
    report = build_report(
        "FleetOps", case.imported, case.analysis, case.generation, review, "approved_only"
    )
    text = export_markdown(report).decode()
    assert "EDITORIALLY APPROVED STATEMENTS ONLY" in text
    assert "Administrators can now enroll" not in text
    assert "Invented speed improvement" not in text
    audit = json.loads(export_json(report))
    assert len(audit["generation"]["claims"]) == 3
    assert len(audit["editorial"]["items"]) == 3
    assert audit["editorial"]["items"][0]["review_status"] == "approved"


def test_full_json_round_trips_original_records_nested_references_and_metadata(case):
    report = build_report("FleetOps", case.imported, case.analysis, case.generation, case.review)
    encoded = export_json(report)
    assert ReleaseReport.model_validate_json(encoded) == report
    audit = json.loads(encoded)
    assert json.loads(audit["imports"]["artifacts"][0]["original_record_json"])["custom"] == {
        "nested": ["preserved"]
    }
    assert isinstance(audit["analysis"]["findings"][0]["source_references"][0], dict)
    assert "[object Object]" not in encoded.decode()
    trace = json.loads(export_json(report, trace_only=True))
    assert trace["items"][0]["current"]["claim"]["evidence"][0]["artifact_id"] == "FLEET-142"
    assert trace["model_digest"] == "a" * 64
    assert trace["source_snapshot_sha256"] == case.generation.source_snapshot_sha256
    assert "reviewer" in trace["items"][0]


def test_answer_attribution_is_separate_from_original_sources(case):
    before = case.imported.model_dump_json()
    with pytest.raises(ValueError):
        answer_question(case.review, "Q-001", "", "Alex", True)
    review = answer_question(
        case.review, "Q-001", "Engineering confirmed a staged rollout.", "Alex", True
    )
    report = build_report("FleetOps", case.imported, case.analysis, case.generation, review)
    text = export_markdown(report).decode()
    assert "Human\\-entered answer" in text and "Attributed to: Alex" in text
    assert case.imported.model_dump_json() == before
    reopened = answer_question(review, "Q-001", "Needs release sign-off.", "Alex", False)
    assert reopened.questions[0].status == "unresolved"


def test_report_does_not_accept_another_generation_or_unknown_modes(case):
    other = case.generation.model_copy(update={"created_at": "2026-10-15T00:00:00+00:00"})
    with pytest.raises(ValueError, match="different generation"):
        build_report("FleetOps", case.imported, case.analysis, other, case.review)
    with pytest.raises(ValueError):
        build_report("", case.imported, case.analysis, case.generation, case.review)
    with pytest.raises(ValueError):
        build_report("FleetOps", case.imported, case.analysis, case.generation, case.review, "bad")


def test_untrusted_markup_is_inert_in_markdown_and_html(case):
    attack = '<img src="https://example.invalid/track" onerror="alert(1)"><script>alert(1)</script> ![remote](https://example.invalid/x)'
    review = revise_item(
        case.review,
        "NOTE-001",
        case.review.items[0].current.claim.model_copy(update={"text": attack}),
        case.imported,
        case.analysis,
        "Alex",
    )
    report = build_report(attack[:190], case.imported, case.analysis, case.generation, review)
    markdown, page = export_markdown(report).decode(), export_html(report).decode()
    assert "<script>" not in page and "<img " not in page
    assert "&lt;img" in page
    assert "default-src 'none'" in page and "@media print" in page
    assert "<script>" not in markdown and "![remote]" not in markdown
    assert (
        attack
        in json.loads(export_json(report))["editorial"]["items"][0]["current"]["claim"]["text"]
    )


def test_zip_has_fixed_safe_names_and_valid_json(case):
    report = build_report(
        "../../FleetOps", case.imported, case.analysis, case.generation, case.review
    )
    with ZipFile(BytesIO(export_package(report))) as archive:
        assert archive.testzip() is None
        assert set(archive.namelist()) == {
            "release-report.md",
            "customer-release-notes.md",
            "technical-release-notes.md",
            "complete-analysis.json",
            "traceability.json",
            "print-report.html",
            "README.txt",
        }
        assert all(".." not in name for name in archive.namelist())
        assert (
            json.loads(archive.read("complete-analysis.json"))["generation"]["release_id"]
            == "2.4.0"
        )
        assert "Print / Save as PDF" in archive.read("README.txt").decode()
        assert b"Customer release notes" in archive.read("customer-release-notes.md")
        assert b"Technical release notes" in archive.read("technical-release-notes.md")


def test_ui_existing_draft_can_export_review_and_invalidate_approval(case):
    from streamlit.testing.v1 import AppTest

    app = AppTest.from_file(
        Path(__file__).resolve().parents[1] / "app.py", default_timeout=30
    ).run()
    app.session_state["import_result"] = case.imported
    app.session_state["analysis_result"] = case.analysis
    app.session_state["generated_release"] = case.generation
    app.run()
    assert not app.exception
    assert len(app.get("download_button")) == 7
    app.text_area(key="editorial_NOTE-001_note").set_value("Compared source and wording.")
    app.selectbox(key="editorial_NOTE-001_decision").select("approved")
    app.checkbox(key="editorial_NOTE-001_verified").check()
    next(b for b in app.button if b.label == "Save editorial decision").click().run()
    assert not app.exception
    assert app.session_state["editorial_review"].items[0].review_status == "approved"
    app.radio(key="report_mode").set_value("approved_only").run()
    assert len(app.get("download_button")) == 7
    app.text_area(key="editorial_NOTE-001_text").set_value(
        "Adds an administrator enrollment workflow."
    )
    next(b for b in app.button if b.label == "Save wording changes").click().run()
    assert not app.exception
    assert app.session_state["editorial_review"].items[0].review_status == "pending"
    assert not app.checkbox(key="editorial_NOTE-001_verified").value
    assert len(app.get("download_button")) == 0
    app.radio(key="report_mode").set_value("draft").run()
    assert len(app.get("download_button")) == 7


def test_ui_unsaved_material_edit_cannot_approve_in_same_click(case):
    from streamlit.testing.v1 import AppTest

    app = AppTest.from_file(
        Path(__file__).resolve().parents[1] / "app.py", default_timeout=30
    ).run()
    app.session_state["import_result"] = case.imported
    app.session_state["analysis_result"] = case.analysis
    app.session_state["generated_release"] = case.generation
    app.run()
    app.text_area(key="editorial_NOTE-001_text").set_value(
        "Adds an administrator enrollment workflow."
    )
    app.text_area(key="editorial_NOTE-001_note").set_value("Checked revised wording.")
    app.selectbox(key="editorial_NOTE-001_decision").select("approved")
    app.checkbox(key="editorial_NOTE-001_verified").check()
    next(b for b in app.button if b.label == "Save editorial decision").click().run()
    assert not app.exception
    assert app.session_state["editorial_review"].items[0].review_status == "pending"
    assert (
        app.session_state["editorial_review"].items[0].current.claim.text
        == "Adds an administrator enrollment workflow."
    )
