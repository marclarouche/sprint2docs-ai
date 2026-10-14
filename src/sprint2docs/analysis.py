"""Deterministic, reviewable analysis. Sources are never modified or merged."""

from collections import defaultdict
from typing import Literal

from pydantic import Field

from .models import ImportResult, Model, ReviewStatus, SourceArtifact, SourceReference

Category = Literal[
    "New Feature",
    "Enhancement",
    "Bug Fix",
    "Security Update",
    "Performance Improvement",
    "Breaking Change",
    "Internal Maintenance",
    "Documentation Only",
    "Unknown",
]
Audience = Literal[
    "Customer-facing",
    "Administrator-facing",
    "Developer-facing",
    "Internal-only",
    "Uncertain",
]
CATEGORIES: tuple[Category, ...] = (
    "New Feature",
    "Enhancement",
    "Bug Fix",
    "Security Update",
    "Performance Improvement",
    "Breaking Change",
    "Internal Maintenance",
    "Documentation Only",
    "Unknown",
)
AUDIENCES: tuple[Audience, ...] = (
    "Customer-facing",
    "Administrator-facing",
    "Developer-facing",
    "Internal-only",
    "Uncertain",
)
TYPE_RULES: dict[str, Category] = {
    "new_feature": "New Feature",
    "feature": "New Feature",
    "added": "New Feature",
    "enhancement": "Enhancement",
    "changed": "Enhancement",
    "bug_fix": "Bug Fix",
    "fixed": "Bug Fix",
    "security_update": "Security Update",
    "security": "Security Update",
    "performance_improvement": "Performance Improvement",
    "performance": "Performance Improvement",
    "breaking_change": "Breaking Change",
    "internal_maintenance": "Internal Maintenance",
    "documentation_only": "Documentation Only",
}
AUDIENCE_RULES: dict[str, Audience] = {
    "customer-facing": "Customer-facing",
    "administrator-facing": "Administrator-facing",
    "developer-facing": "Developer-facing",
    "internal-only": "Internal-only",
}


class Finding(Model):
    change_id: str
    category: Category
    category_rationale: str
    audience: Audience
    audience_rationale: str
    source_references: tuple[SourceReference, ...] = Field(min_length=1)
    review_status: ReviewStatus = "pending"
    reviewer_note: str | None = None


class Relationship(Model):
    left_key: str
    right_key: str
    reasons: tuple[str, ...]
    duplicate_candidate: bool
    review_status: ReviewStatus = "pending"


class UnresolvedReference(Model):
    artifact_key: str
    related_id: str
    reason: Literal["missing_target", "ambiguous_target", "release_conflict"]


class AnalysisResult(Model):
    rules_version: Literal["deterministic-1.0"] = "deterministic-1.0"
    findings: tuple[Finding, ...]
    relationships: tuple[Relationship, ...]
    unresolved_references: tuple[UnresolvedReference, ...]


def classify(source: SourceArtifact) -> Finding:
    value = (source.change_type or "").strip().lower().replace(" ", "_").replace("-", "_")
    category = TYPE_RULES.get(value, "Unknown")
    audiences = {
        AUDIENCE_RULES[label.lower()]
        for label in source.labels or ()
        if label.lower() in AUDIENCE_RULES
    }
    audience: Audience = next(iter(audiences)) if len(audiences) == 1 else "Uncertain"
    return Finding(
        change_id=f"CHG-{source.artifact_key}",
        category=category,
        category_rationale=(
            "Mapped explicit source change_type using deterministic rules."
            if category != "Unknown"
            else "Missing or unrecognized source change_type."
        ),
        audience=audience,
        audience_rationale=(
            "Explicit audience label; human verification required."
            if len(audiences) == 1
            else "No single explicit audience label; title, completion status and category do not establish audience."
        ),
        source_references=(
            SourceReference(
                artifact_key=source.artifact_key,
                artifact_id=source.artifact_id,
                field="change_type",
            ),
            SourceReference(
                artifact_key=source.artifact_key, artifact_id=source.artifact_id, field="labels"
            ),
        ),
    )


def analyze(result: ImportResult) -> AnalysisResult:
    by_id: dict[str, list[SourceArtifact]] = defaultdict(list)
    by_title: dict[tuple[str | None, str], list[SourceArtifact]] = defaultdict(list)
    edges: dict[tuple[str, str], set[str]] = defaultdict(set)
    unresolved: list[UnresolvedReference] = []
    for source in result.artifacts:
        by_id[source.artifact_id].append(source)
        by_title[(source.release_id, " ".join(source.title.casefold().split()))].append(source)

    def connect(left: SourceArtifact, right: SourceArtifact, reason: str) -> None:
        if left.artifact_key != right.artifact_key:
            pair = tuple(sorted((left.artifact_key, right.artifact_key)))
            edges[(pair[0], pair[1])].add(reason)

    for group in by_id.values():
        for i, left in enumerate(group):
            for right in group[i + 1 :]:
                connect(left, right, "shared_source_identifier")
    for group in by_title.values():
        for i, left in enumerate(group):
            for right in group[i + 1 :]:
                connect(left, right, "matching_title_and_release")
    for source in result.artifacts:
        for related_id in source.related_ids or ():
            targets = [
                t for t in by_id.get(related_id, ()) if t.artifact_key != source.artifact_key
            ]
            compatible = [
                t
                for t in targets
                if not source.release_id or not t.release_id or source.release_id == t.release_id
            ]
            reason: Literal["missing_target", "ambiguous_target", "release_conflict"] | None = None
            if not targets:
                reason = "missing_target"
            elif not compatible:
                reason = "release_conflict"
            elif len(compatible) > 1:
                reason = "ambiguous_target"
            if reason:
                unresolved.append(
                    UnresolvedReference(
                        artifact_key=source.artifact_key, related_id=related_id, reason=reason
                    )
                )
            for target in compatible:
                connect(source, target, "explicit_related_id")
    return AnalysisResult(
        findings=tuple(classify(a) for a in result.artifacts),
        relationships=tuple(
            Relationship(
                left_key=left,
                right_key=right,
                reasons=tuple(sorted(reasons)),
                duplicate_candidate=bool(
                    reasons & {"shared_source_identifier", "matching_title_and_release"}
                ),
            )
            for (left, right), reasons in sorted(edges.items())
        ),
        unresolved_references=tuple(unresolved),
    )


def review_finding(
    finding: Finding,
    category: Category,
    audience: Audience,
    status: ReviewStatus,
    note: str,
) -> Finding:
    """Validate an explicit human decision, retaining the original rule rationale."""
    if not note.strip():
        raise ValueError("A review note is required.")
    return Finding.model_validate(
        {
            **finding.model_dump(),
            "category": category,
            "audience": audience,
            "review_status": status,
            "reviewer_note": note.strip(),
        }
    )
