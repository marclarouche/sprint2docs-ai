"""Bounded AI response schemas and source validation outcomes."""

from typing import Any, Literal

from pydantic import Field

from .analysis import Category
from .models import Model, Provenance


class Evidence(Model):
    artifact_key: str = Field(min_length=1, max_length=128)
    artifact_id: str = Field(min_length=1, max_length=128)
    field: Literal["title", "description"]
    excerpt: str = Field(min_length=1, max_length=500)


class DraftClaim(Model):
    audience: Literal["customer", "technical"]
    category: Category
    text: str = Field(min_length=1, max_length=500)
    evidence: tuple[Evidence, ...] = Field(min_length=1, max_length=3)


class Clarification(Model):
    question: str = Field(min_length=1, max_length=500)
    evidence: tuple[Evidence, ...] = Field(min_length=1, max_length=3)


class DraftResponse(Model):
    claims: tuple[DraftClaim, ...] = Field(max_length=16)
    questions: tuple[Clarification, ...] = Field(max_length=8)


class ValidatedClaim(Model):
    claim: DraftClaim
    status: Literal["requires_editorial_verification", "unsupported"]
    issues: tuple[str, ...]
    provenance: tuple[Provenance, ...]
    review_status: Literal["pending"] = "pending"


class ValidatedQuestion(Model):
    question: Clarification
    provenance: tuple[Provenance, ...]
    status: Literal["unresolved"] = "unresolved"


class GenerationSettings(Model):
    model: str = Field(min_length=1, max_length=200)
    timeout_seconds: int = Field(default=120, ge=1, le=300)
    temperature: Literal[0] = 0
    seed: int = Field(default=42, ge=0)
    num_predict: int = Field(default=3000, ge=128, le=8000)
    num_ctx: int = Field(default=16384, ge=4096, le=32768)
    batch_records: int = Field(default=4, ge=1, le=8)
    max_context_chars: int = Field(default=24000, ge=2000, le=48000)
    max_records: int = Field(default=40, ge=1, le=100)


class GenerationResult(Model):
    release_id: str
    created_at: str
    tool_version: str = "0.1.0"
    prompt_version: str = "release-notes-1.0"
    validator_version: str = "source-excerpts-1.1"
    settings: GenerationSettings
    model_digest: str
    source_snapshot_sha256: str
    analysis_snapshot_sha256: str
    source_keys: tuple[str, ...]
    claims: tuple[ValidatedClaim, ...]
    questions: tuple[ValidatedQuestion, ...]
    diagnostics: tuple[str, ...]
    status: Literal["complete", "partial", "failed"]


def response_schema(record_count: int) -> dict[str, Any]:
    """Bound generated items to the size of this request, not the whole release."""
    schema = DraftResponse.model_json_schema()
    schema["properties"]["claims"]["maxItems"] = min(16, record_count * 2)
    schema["properties"]["questions"]["maxItems"] = min(8, record_count)
    return schema
