"""Bounded, deterministic CSV/JSON/Markdown imports; source data is never executed."""

import csv
import hashlib
import io
import json
import re
from collections.abc import Sequence
from pathlib import PurePosixPath
from typing import Any, Literal, cast

from pydantic import ValidationError

from .models import (
    ArtifactRecord,
    ArtifactType,
    DocumentationInventoryEntry,
    ImportedFile,
    ImportInput,
    ImportLimits,
    ImportResult,
    InventoryRecord,
    Provenance,
    SourceArtifact,
    ValidationIssue,
)
from .normalizer import normalize


class ImportFailure(ValueError):
    """Only static diagnostic codes; never retain a sensitive parser exception."""


def safe_name(filename: str) -> str:
    name = PurePosixPath(filename.replace("\\", "/")).name
    return "".join(c for c in name if c.isprintable())[:200] or "upload"


def issue(
    code: str,
    filename: str,
    *,
    severity: Literal["error", "warning"] = "error",
    record: int | None = None,
    field: str | None = None,
) -> ValidationIssue:
    messages = {
        "invalid_record": "A required field is missing or a field has an invalid type or value.",
        "missing_optional": "Optional source information is missing; review before drafting.",
        "metadata_retained": "Unrecognized metadata was retained in the original record or file metadata.",
        "duplicate_identifier": "A source identifier is repeated; records are retained separately for review.",
    }
    return ValidationIssue(
        severity=severity,
        code=code,
        filename=filename,
        record_number=record,
        field=field,
        message=messages.get(
            code,
            "Unable to import this file. Check the supported schema, encoding, and resource limits.",
        ),
    )


def canonical(record: object) -> str:
    return json.dumps(record, ensure_ascii=False, sort_keys=True, allow_nan=False)


def decode(data: bytes, limits: ImportLimits) -> str:
    if not data or len(data) > limits.max_file_bytes:
        raise ImportFailure("file_size_limit")
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise ImportFailure("invalid_utf8") from None
    if len(text) > limits.max_text_chars:
        raise ImportFailure("text_limit")
    if any(ord(c) < 32 and c not in "\n\r\t" for c in text):
        raise ImportFailure("binary_content")
    return text


def json_records(text: str, limits: ImportLimits) -> tuple[str, list[Any], str]:
    depth = 0
    inside = escaped = False
    for char in text:
        if inside:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                inside = False
        elif char == '"':
            inside = True
        elif char in "[{":
            depth += 1
            if depth > limits.max_json_depth:
                raise ImportFailure("json_depth_limit")
        elif char in "]}":
            depth -= 1

    def pairs(values: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in values:
            if key in result:
                raise ImportFailure("duplicate_json_key")
            result[key] = value
        return result

    def invalid_constant(value: str) -> None:
        raise ImportFailure("nonfinite_json_number")

    try:
        data = json.loads(text, object_pairs_hook=pairs, parse_constant=invalid_constant)
    except (json.JSONDecodeError, RecursionError, ValueError) as error:
        if isinstance(error, ImportFailure):
            raise
        raise ImportFailure("invalid_json") from None
    if not isinstance(data, dict) or data.get("schema_version") != "1.0":
        raise ImportFailure("invalid_json_envelope")
    kind = data.get("artifact_type")
    records = data.get("records")
    if kind not in {"ticket", "pull_request", "documentation_inventory"} or not isinstance(
        records, list
    ):
        raise ImportFailure("unsupported_json_schema")
    if len(records) > limits.max_records:
        raise ImportFailure("record_limit")
    metadata = {
        k: v for k, v in data.items() if k not in {"schema_version", "artifact_type", "records"}
    }
    try:
        return kind, records, canonical(metadata)
    except ValueError:
        raise ImportFailure("nonfinite_json_number") from None


def csv_records(
    text: str, limits: ImportLimits
) -> list[tuple[dict[str, Any], int | None, int | None]]:
    # A field may span physical lines; line_start/end refer to those original lines.
    reader = csv.reader(io.StringIO(text, newline=""), strict=True)
    try:
        headers = next(reader)
        if (
            len(set(headers)) != len(headers)
            or not {"id", "title"}.issubset(headers)
            or any(not h for h in headers)
        ):
            raise ImportFailure("invalid_csv_headers")
        records: list[tuple[dict[str, Any], int | None, int | None]] = []
        previous = reader.line_num
        for row in reader:
            start = previous + 1
            previous = reader.line_num
            if not row:
                continue
            if len(row) != len(headers):
                raise ImportFailure("invalid_csv_row_shape")
            record: dict[str, Any] = dict(zip(headers, row, strict=True))
            for field in ArtifactRecord.model_fields:
                if field in record and record[field] == "":
                    record[field] = None
            for field in ("related_ids", "labels"):
                if field in record and isinstance(record[field], str):
                    record[field] = [value.strip() for value in record[field].split(";")]
            # Store the literal CSV values as well as the explicitly mapped values.
            record["_original_csv"] = dict(zip(headers, row, strict=True))
            records.append((record, start, reader.line_num))
            if len(records) > limits.max_records:
                raise ImportFailure("record_limit")
        return records
    except (csv.Error, StopIteration):
        raise ImportFailure("invalid_csv") from None


def markdown_records(
    text: str, limits: ImportLimits
) -> list[tuple[dict[str, Any], int | None, int | None]]:
    records: list[tuple[dict[str, Any], int | None, int | None]] = []
    release: str | None = None
    category: str | None = None
    current: dict[str, Any] | None = None
    lines: list[str] = []
    start = end = 0

    def flush() -> None:
        nonlocal current, lines
        if current is not None:
            description = [
                line.strip()
                for line in lines[1:]
                if line.strip() and not line.strip().startswith("Related:")
            ]
            current["description"] = "\n".join(description) or None
            current["raw_markdown"] = "\n".join(lines)
            records.append((current, start, end))
            if len(records) > limits.max_records:
                raise ImportFailure("record_limit")
        current = None
        lines = []

    for number, line in enumerate(text.splitlines(), 1):
        if line.startswith("## "):
            flush()
            match = re.fullmatch(r"## (?:\[([^\]]+)\]|([^\s]+))", line)
            if not match:
                raise ImportFailure("invalid_markdown_release")
            release = match.group(1) or match.group(2)
            category = None
        elif line.startswith("### "):
            flush()
            category = line[4:].strip() or None
        elif line.startswith("- "):
            flush()
            match = re.fullmatch(r"- \[([^\]\s]+)\] (.+)", line)
            if not match or release is None:
                raise ImportFailure("invalid_markdown_entry")
            current = {
                "id": match.group(1),
                "title": match.group(2),
                "release_id": release,
                "change_type": category,
            }
            start = end = number
            lines = [line]
        elif current is not None and (line.startswith("  ") or not line.strip()):
            lines.append(line)
            end = number
            if line.strip().startswith("Related:"):
                current["related_ids"] = [value.strip() for value in line.strip()[8:].split(",")]
        elif current is not None:
            raise ImportFailure("unsupported_markdown_continuation")
        elif line.strip() and not line.startswith("# "):
            raise ImportFailure("unsupported_markdown_content")
    flush()
    if not records:
        raise ImportFailure("empty_markdown")
    return records


def _import_file(data: bytes, filename: str, limits: ImportLimits) -> ImportResult:
    name = safe_name(filename)
    extension = PurePosixPath(name).suffix.lower().lstrip(".")
    if extension not in {"csv", "json", "md"}:
        raise ImportFailure("unsupported_format")
    text = decode(data, limits)
    digest = hashlib.sha256(data).hexdigest()
    metadata = "{}"
    records: list[tuple[Any, int | None, int | None]]
    if extension == "csv":
        kind = "ticket"
        records = csv_records(text, limits)
    elif extension == "md":
        kind = "changelog"
        records = markdown_records(text, limits)
    else:
        kind, raw_records, metadata = json_records(text, limits)
        records = [(record, None, None) for record in raw_records]
    if not records:
        raise ImportFailure("empty_records")
    artifacts = []
    inventory = []
    issues = []
    known_ids: set[str] = set()
    if metadata != "{}":
        issues.append(issue("metadata_retained", name, severity="warning"))
    for number, (raw, start, end) in enumerate(records, 1):
        provenance = Provenance(
            filename=name, file_sha256=digest, record_number=number, line_start=start, line_end=end
        )
        key = hashlib.sha256(f"{digest}:{kind}:{number}".encode()).hexdigest()
        record_model = InventoryRecord if kind == "documentation_inventory" else ArtifactRecord
        try:
            record = record_model.model_validate(raw)
        except ValidationError as error:
            fields = sorted(
                {
                    str(e["loc"][0])
                    for e in error.errors(include_input=False)
                    if e["loc"] and str(e["loc"][0]) in record_model.model_fields
                }
            )
            failed_fields: list[str | None] = list(fields) if fields else [None]
            for field in failed_fields:
                issues.append(issue("invalid_record", name, record=number, field=field))
            continue
        # Keep the literal record; _original_csv preserves pre-mapping strings.
        original = raw.get("_original_csv", raw) if isinstance(raw, dict) else raw
        unknown = tuple(
            sorted(
                k
                for k in raw
                if k not in record_model.model_fields and k not in {"_original_csv", "raw_markdown"}
            )
        )
        if unknown:
            issues.append(issue("metadata_retained", name, severity="warning", record=number))
        if isinstance(record, InventoryRecord):
            identifier = record.document_id
            inventory.append(
                DocumentationInventoryEntry(
                    document_key=key,
                    document_id=identifier,
                    title=record.title,
                    document_type=record.document_type,
                    component=record.component,
                    covered_features=tuple(record.covered_features)
                    if record.covered_features is not None
                    else None,
                    description=record.description,
                    section_ids=tuple(record.section_ids)
                    if record.section_ids is not None
                    else None,
                    provenance=provenance,
                    original_record_json=canonical(original),
                    unrecognized_fields=unknown,
                )
            )
        else:
            identifier = record.id
            artifacts.append(
                SourceArtifact(
                    artifact_key=key,
                    artifact_id=identifier,
                    artifact_type=cast(ArtifactType, kind),
                    title=record.title,
                    description=record.description,
                    status=record.status,
                    release_id=record.release_id,
                    change_type=record.change_type,
                    component=record.component,
                    related_ids=tuple(record.related_ids)
                    if record.related_ids is not None
                    else None,
                    labels=tuple(record.labels) if record.labels is not None else None,
                    url=record.url,
                    provenance=provenance,
                    original_record_json=canonical(original),
                    unrecognized_fields=unknown,
                )
            )
        for field in record_model.model_fields:
            if field not in {"id", "document_id", "title"} and getattr(record, field) in (None, ""):
                issues.append(
                    issue("missing_optional", name, severity="warning", record=number, field=field)
                )
        if identifier in known_ids:
            issues.append(issue("duplicate_identifier", name, severity="warning", record=number))
        known_ids.add(identifier)
    imported = ImportedFile(
        filename=name,
        file_sha256=digest,
        format=cast(Literal["csv", "json", "md"], extension),
        records_seen=len(records),
        envelope_metadata_json=metadata,
    )
    return ImportResult(
        files=(imported,),
        artifacts=tuple(artifacts),
        inventory=tuple(inventory),
        changes=tuple(normalize(a) for a in artifacts),
        issues=tuple(issues),
    )


def import_file(data: bytes, filename: str, limits: ImportLimits | None = None) -> ImportResult:
    """File-level errors reject the file; invalid records reject only those records."""
    try:
        return _import_file(data, filename, limits or ImportLimits())
    except ImportFailure as error:
        return ImportResult(issues=(issue(str(error), safe_name(filename)),))
    except (ValueError, TypeError, RecursionError, OverflowError):
        return ImportResult(issues=(issue("invalid_content", safe_name(filename)),))


def import_batch(files: Sequence[ImportInput], limits: ImportLimits | None = None) -> ImportResult:
    """Enforce whole-session budgets before processing; never collapse records."""
    budget = limits or ImportLimits()
    if len(files) > budget.max_files or sum(len(f.data) for f in files) > budget.max_batch_bytes:
        return ImportResult(issues=(issue("batch_size_limit", "batch"),))
    # Count decoded characters before processing so a batch over budget imports nothing.
    texts = 0
    try:
        for file in files:
            texts += len(decode(file.data, budget))
        if texts > budget.max_text_chars:
            raise ImportFailure("batch_text_limit")
    except ImportFailure as error:
        return ImportResult(issues=(issue(str(error), "batch"),))
    results = []
    remaining = budget.max_records
    for file in files:
        if remaining == 0:
            results.append(ImportResult(issues=(issue("record_limit", safe_name(file.filename)),)))
            continue
        result = import_file(
            file.data, file.filename, budget.model_copy(update={"max_records": remaining})
        )
        remaining -= sum(f.records_seen for f in result.files)
        if any(i.code == "record_limit" for i in result.issues):
            remaining = 0
        results.append(result)
    artifacts = tuple(a for result in results for a in result.artifacts)
    inventory = tuple(d for result in results for d in result.inventory)
    issues = [i for result in results for i in result.issues]
    seen: set[tuple[str, str]] = set()
    for result in results:
        file_ids: set[tuple[str, str]] = set()
        entities: tuple[SourceArtifact | DocumentationInventoryEntry, ...] = (
            *result.artifacts,
            *result.inventory,
        )
        for entity in entities:
            identifier = (
                (entity.artifact_type, entity.artifact_id)
                if isinstance(entity, SourceArtifact)
                else ("documentation_inventory", entity.document_id)
            )
            if identifier in seen:
                issues.append(
                    issue(
                        "duplicate_identifier",
                        entity.provenance.filename,
                        severity="warning",
                        record=entity.provenance.record_number,
                    )
                )
            file_ids.add(identifier)
        seen.update(file_ids)
    return ImportResult(
        files=tuple(f for result in results for f in result.files),
        artifacts=artifacts,
        inventory=inventory,
        changes=tuple(c for result in results for c in result.changes),
        issues=tuple(issues),
    )
