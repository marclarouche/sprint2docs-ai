"""Copy source-supported fields without classification, merging, or inference."""

from .models import NormalizedChange, SourceArtifact, SourceReference


def normalize(artifact: SourceArtifact) -> NormalizedChange:
    return NormalizedChange(
        change_id=f"CHG-{artifact.artifact_key}",
        source_references=(
            SourceReference(artifact_key=artifact.artifact_key, artifact_id=artifact.artifact_id),
        ),
        provenance=(artifact.provenance,),
        source_type=artifact.artifact_type,
        title=artifact.title,
        description=artifact.description,
        status=artifact.status,
        release_id=artifact.release_id,
        change_type=artifact.change_type,
        component=artifact.component,
        related_ids=artifact.related_ids,
        labels=artifact.labels,
        missing_fields=tuple(
            field
            for field in (
                "description",
                "status",
                "release_id",
                "change_type",
                "component",
                "related_ids",
                "labels",
                "url",
            )
            if getattr(artifact, field) in (None, "")
        ),
    )
