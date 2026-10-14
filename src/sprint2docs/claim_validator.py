"""Check evidence existence and exact excerpts; never certify semantic truth."""

import re

from .generation_models import DraftClaim, Evidence, ValidatedClaim
from .models import Provenance, SourceArtifact


def validate_evidence(
    evidence: tuple[Evidence, ...],
    sources: tuple[SourceArtifact, ...],
) -> tuple[tuple[str, ...], tuple[Provenance, ...]]:
    by_key = {s.artifact_key: s for s in sources}
    issues: list[str] = []
    provenance: list[Provenance] = []
    for ref in evidence:
        source = by_key.get(ref.artifact_key)
        if source is None:
            issues.append("unknown_source_key")
            continue
        if ref.artifact_id != source.artifact_id:
            issues.append("source_identifier_mismatch")
        text = getattr(source, ref.field)
        if not ref.excerpt.strip() or text is None or ref.excerpt not in text:
            issues.append("excerpt_not_in_source_field")
        provenance.append(source.provenance)
    return tuple(sorted(set(issues))), tuple(provenance)


def validate_claim(claim: DraftClaim, sources: tuple[SourceArtifact, ...]) -> ValidatedClaim:
    errors, provenance = validate_evidence(claim.evidence, sources)
    issues = list(errors)
    excerpts = " ".join(e.excerpt for e in claim.evidence)
    # A narrow guard for invented quantities and commands; not an entailment proof.
    if any(number not in excerpts for number in re.findall(r"\b\d+(?:\.\d+)?%?", claim.text)):
        issues.append("unmatched_numeric_detail")
    if "`" in claim.text and claim.text not in excerpts:
        issues.append("procedure_requires_verification")
    return ValidatedClaim(
        claim=claim,
        status="unsupported" if issues else "requires_editorial_verification",
        issues=tuple(sorted(set(issues))),
        provenance=provenance,
    )
