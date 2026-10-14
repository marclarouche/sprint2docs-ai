"""Immutable domain schemas; no UI, network, or source execution."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

ArtifactType = Literal["ticket", "pull_request", "changelog"]
ReviewStatus = Literal["pending", "approved", "rejected", "needs_clarification"]


class Model(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)
    schema_version: Literal["1.0"] = "1.0"


class Provenance(Model):
    filename: str
    file_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    record_number: int = Field(ge=1)
    line_start: int | None = Field(default=None, ge=1)
    line_end: int | None = Field(default=None, ge=1)


class ValidationIssue(Model):
    severity: Literal["warning", "error"]
    code: str
    message: str
    filename: str
    record_number: int | None = None
    field: str | None = None


class SourceArtifact(Model):
    artifact_key: str
    artifact_id: str = Field(min_length=1, max_length=128)
    artifact_type: ArtifactType
    title: str = Field(min_length=1, max_length=1000)
    description: str | None = None
    status: str | None = None
    release_id: str | None = None
    change_type: str | None = None
    component: str | None = None
    related_ids: tuple[str, ...] | None = None
    labels: tuple[str, ...] | None = None
    url: str | None = None
    provenance: Provenance
    original_record_json: str
    unrecognized_fields: tuple[str, ...] = ()


class SourceReference(Model):
    artifact_key: str
    artifact_id: str
    field: str | None = None


class SourceGroundedClaim(Model):
    """Future claim container, not populated during Milestone 1."""

    text: str
    source_references: tuple[SourceReference, ...] = Field(min_length=1)
    support_status: Literal["requires_editorial_verification"] = "requires_editorial_verification"
    review_status: ReviewStatus = "pending"


class NormalizedChange(Model):
    change_id: str
    source_references: tuple[SourceReference, ...] = Field(min_length=1)
    provenance: tuple[Provenance, ...] = Field(min_length=1)
    source_type: ArtifactType
    title: str
    description: str | None
    status: str | None
    release_id: str | None
    change_type: str | None
    component: str | None
    related_ids: tuple[str, ...] | None
    labels: tuple[str, ...] | None
    missing_fields: tuple[str, ...] = ()
    documentation_ids: tuple[str, ...] = ()
    claims: tuple[SourceGroundedClaim, ...] = ()
    review_status: ReviewStatus = "pending"


class DocumentationInventoryEntry(Model):
    document_key: str
    document_id: str
    title: str
    document_type: str | None
    component: str | None
    covered_features: tuple[str, ...] | None
    description: str | None
    section_ids: tuple[str, ...] | None
    provenance: Provenance
    original_record_json: str
    unrecognized_fields: tuple[str, ...] = ()


class ImportedFile(Model):
    filename: str
    file_sha256: str
    format: Literal["csv", "json", "md"]
    records_seen: int
    envelope_metadata_json: str = "{}"


class ImportResult(Model):
    files: tuple[ImportedFile, ...] = ()
    artifacts: tuple[SourceArtifact, ...] = ()
    inventory: tuple[DocumentationInventoryEntry, ...] = ()
    changes: tuple[NormalizedChange, ...] = ()
    issues: tuple[ValidationIssue, ...] = ()

    @property
    def error_count(self) -> int:
        return sum(issue.severity == "error" for issue in self.issues)

    @property
    def warning_count(self) -> int:
        return sum(issue.severity == "warning" for issue in self.issues)


class ImportLimits(Model):
    max_file_bytes: int = Field(default=10 * 1024 * 1024, ge=1, le=10 * 1024 * 1024)
    max_batch_bytes: int = Field(default=25 * 1024 * 1024, ge=1, le=50 * 1024 * 1024)
    max_files: int = Field(default=10, ge=1, le=50)
    max_records: int = Field(default=2000, ge=1, le=10000)
    max_text_chars: int = Field(default=2_000_000, ge=1, le=10_000_000)
    max_json_depth: int = Field(default=20, ge=1, le=50)


class ImportInput(Model):
    filename: str
    data: bytes


class ArtifactRecord(BaseModel):
    """Documented input record; unknown metadata remains in the original record."""

    model_config = ConfigDict(extra="allow", strict=True)
    id: str = Field(min_length=1, max_length=128)
    title: str = Field(min_length=1, max_length=1000)
    description: str | None = None
    status: str | None = None
    release_id: str | None = None
    change_type: str | None = None
    component: str | None = None
    related_ids: list[str] | None = None
    labels: list[str] | None = None
    url: str | None = None

    @field_validator("id")
    @classmethod
    def valid_id(cls, value: str) -> str:
        if any(c.isspace() for c in value):
            raise ValueError("invalid_identifier")
        return value

    @field_validator("title")
    @classmethod
    def nonblank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("blank_title")
        return value

    @field_validator("related_ids", "labels")
    @classmethod
    def nonblank_items(cls, value: list[str] | None) -> list[str] | None:
        if value is not None and any(not item.strip() for item in value):
            raise ValueError("blank_list_item")
        return value


class InventoryRecord(BaseModel):
    model_config = ConfigDict(extra="allow", strict=True)
    document_id: str = Field(min_length=1, max_length=128)
    title: str = Field(min_length=1, max_length=1000)
    document_type: str | None = None
    component: str | None = None
    covered_features: list[str] | None = None
    description: str | None = None
    section_ids: list[str] | None = None

    @field_validator("document_id", "title")
    @classmethod
    def nonblank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("blank_required_field")
        return value
