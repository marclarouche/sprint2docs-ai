"""Explicit editorial decisions, independent of analysis approvals and UI state."""

import hashlib
import re
from datetime import UTC, datetime
from typing import Literal

from .ai_writer import snapshot
from .analysis import AnalysisResult
from .claim_validator import validate_claim
from .generation_models import DraftClaim, GenerationResult, ValidatedClaim
from .models import ImportResult, Model, ReviewStatus


def generation_key(generated: GenerationResult) -> str:
    return hashlib.sha256(generated.model_dump_json().encode()).hexdigest()


class EditorialItem(Model):
    item_id: str
    source_claim_index: int
    current: ValidatedClaim
    review_status: ReviewStatus = "pending"
    reviewer: str | None = None
    review_note: str | None = None
    reviewed_at: str | None = None


class QuestionReview(Model):
    question_id: str
    source_question_index: int
    status: Literal["unresolved", "resolved"] = "unresolved"
    answer: str | None = None
    answered_by: str | None = None
    answered_at: str | None = None


class ReviewEvent(Model):
    item_id: str
    action: str
    created_at: str
    reviewer: str


class EditorialReview(Model):
    generation_key: str
    items: tuple[EditorialItem, ...]
    questions: tuple[QuestionReview, ...]
    events: tuple[ReviewEvent, ...] = ()
    validator_version: str = "source-excerpts-1.1"


class DuplicateCandidate(Model):
    left_id: str
    right_id: str
    reason: str


def start_review(generated: GenerationResult) -> EditorialReview:
    return EditorialReview(
        generation_key=generation_key(generated),
        items=tuple(
            EditorialItem(item_id=f"NOTE-{i + 1:03d}", source_claim_index=i, current=c)
            for i, c in enumerate(generated.claims)
        ),
        questions=tuple(
            QuestionReview(question_id=f"Q-{i + 1:03d}", source_question_index=i)
            for i, _ in enumerate(generated.questions)
        ),
    )


def is_stale(generated: GenerationResult, imported: ImportResult, analysis: AnalysisResult) -> bool:
    return generated.source_snapshot_sha256 != snapshot(
        imported
    ) or generated.analysis_snapshot_sha256 != snapshot(analysis)


def check_review(review: EditorialReview, generated: GenerationResult) -> None:
    if review.generation_key != generation_key(generated):
        raise ValueError("Editorial decisions belong to a different generation.")
    if (
        len(review.items) != len(generated.claims)
        or tuple(i.source_claim_index for i in review.items) != tuple(range(len(generated.claims)))
        or len({i.item_id for i in review.items}) != len(review.items)
        or len(review.questions) != len(generated.questions)
        or tuple(q.source_question_index for q in review.questions)
        != tuple(range(len(generated.questions)))
    ):
        raise ValueError("Editorial review does not match generated items.")


def revise_item(
    review: EditorialReview,
    item_id: str,
    claim: DraftClaim,
    imported: ImportResult,
    analysis: AnalysisResult,
    reviewer: str,
) -> EditorialReview:
    if not claim.text.strip() or not reviewer.strip():
        raise ValueError("Enter nonempty wording and a reviewer name.")
    validated = validate_claim(claim, imported.artifacts)
    cited = {e.artifact_key for e in claim.evidence}
    findings = {f.change_id: f for f in analysis.findings}
    if claim.audience == "customer" and any(
        findings.get(f"CHG-{key}") is not None
        and findings[f"CHG-{key}"].audience == "Internal-only"
        for key in cited
    ):
        validated = validated.model_copy(
            update={
                "status": "unsupported",
                "issues": tuple(
                    sorted(set(validated.issues) | {"internal_source_in_customer_note"})
                ),
            }
        )
    items = list(review.items)
    index = next((i for i, item in enumerate(items) if item.item_id == item_id), None)
    if index is None:
        raise ValueError("Unknown editorial item.")
    previous = items[index]
    changed = claim != previous.current.claim or validated != previous.current
    if not changed:
        return review
    items[index] = previous.model_copy(
        update={
            "current": validated,
            "review_status": "pending",
            "reviewer": None,
            "review_note": None,
            "reviewed_at": None,
        }
    )
    event = ReviewEvent(
        item_id=item_id,
        action="edited_approval_reset",
        created_at=datetime.now(UTC).isoformat(),
        reviewer=reviewer.strip(),
    )
    return review.model_copy(update={"items": tuple(items), "events": review.events + (event,)})


def decide_item(
    review: EditorialReview,
    item_id: str,
    status: ReviewStatus,
    reviewer: str,
    note: str,
    generated: GenerationResult,
    imported: ImportResult,
    analysis: AnalysisResult,
    evidence_verified: bool = False,
) -> EditorialReview:
    check_review(review, generated)
    if status not in ("pending", "approved", "rejected", "needs_clarification"):
        raise ValueError("Unknown editorial decision.")
    if not reviewer.strip() or not note.strip():
        raise ValueError("A reviewer name and decision note are required.")
    items = list(review.items)
    index = next((i for i, item in enumerate(items) if item.item_id == item_id), None)
    if index is None:
        raise ValueError("Unknown editorial item.")
    if status == "approved":
        if is_stale(generated, imported, analysis):
            raise ValueError("Imports or analysis changed. Regenerate before approving wording.")
        if items[index].current.status == "unsupported":
            raise ValueError("Resolve evidence validation issues before approving this statement.")
        if not evidence_verified:
            raise ValueError("Explicitly confirm that you verified the evidence and wording.")
    now = datetime.now(UTC).isoformat()
    items[index] = items[index].model_copy(
        update={
            "review_status": status,
            "reviewer": reviewer.strip(),
            "review_note": note.strip(),
            "reviewed_at": now,
        }
    )
    event = ReviewEvent(
        item_id=item_id, action=f"decision_{status}", created_at=now, reviewer=reviewer.strip()
    )
    return review.model_copy(update={"items": tuple(items), "events": review.events + (event,)})


def answer_question(
    review: EditorialReview,
    question_id: str,
    answer: str,
    reviewer: str,
    resolved: bool,
) -> EditorialReview:
    if not reviewer.strip() or (resolved and not answer.strip()):
        raise ValueError("A resolved question needs an answer and reviewer attribution.")
    questions = list(review.questions)
    index = next((i for i, q in enumerate(questions) if q.question_id == question_id), None)
    if index is None:
        raise ValueError("Unknown clarification question.")
    now = datetime.now(UTC).isoformat()
    questions[index] = questions[index].model_copy(
        update={
            "status": "resolved" if resolved else "unresolved",
            "answer": answer.strip() or None,
            "answered_by": reviewer.strip(),
            "answered_at": now,
        }
    )
    event = ReviewEvent(
        item_id=question_id,
        action="question_resolved" if resolved else "question_reopened",
        created_at=now,
        reviewer=reviewer.strip(),
    )
    return review.model_copy(
        update={"questions": tuple(questions), "events": review.events + (event,)}
    )


def item_warnings(item: EditorialItem, analysis: AnalysisResult) -> tuple[str, ...]:
    warnings: list[str] = []
    claim = item.current.claim
    by_change = {f.change_id: f for f in analysis.findings}
    categories = {
        by_change[f"CHG-{e.artifact_key}"].category
        for e in claim.evidence
        if f"CHG-{e.artifact_key}" in by_change
        and by_change[f"CHG-{e.artifact_key}"].review_status == "approved"
    }
    if categories and claim.category not in categories:
        warnings.append("Category differs from approved source analysis; check the classification.")
    if re.search(
        r"\b(can now|now available|is available|released|deployed|generally available)\b",
        claim.text,
        re.I,
    ):
        warnings.append(
            "Check availability/deployment wording against evidence; completion is not deployment."
        )
    return tuple(warnings)


def duplicate_candidates(
    review: EditorialReview, analysis: AnalysisResult
) -> tuple[DuplicateCandidate, ...]:
    candidates: list[DuplicateCandidate] = []
    links = {
        frozenset((r.left_key, r.right_key))
        for r in analysis.relationships
        if r.review_status != "rejected"
    }
    active = [i for i in review.items if i.review_status != "rejected"]
    for i, left in enumerate(active):
        for right in active[i + 1 :]:
            a, b = left.current.claim, right.current.claim
            if a.audience != b.audience:
                continue
            keys_a, keys_b = (
                {e.artifact_key for e in a.evidence},
                {e.artifact_key for e in b.evidence},
            )
            ids_a, ids_b = {e.artifact_id for e in a.evidence}, {e.artifact_id for e in b.evidence}
            same_text = " ".join(a.text.casefold().split()) == " ".join(b.text.casefold().split())
            related = any(frozenset((x, y)) in links for x in keys_a for y in keys_b)
            if same_text or ids_a & ids_b or related:
                candidates.append(
                    DuplicateCandidate(
                        left_id=left.item_id,
                        right_id=right.item_id,
                        reason="Matching wording or overlapping/related evidence; review before retaining both.",
                    )
                )
    return tuple(candidates)
