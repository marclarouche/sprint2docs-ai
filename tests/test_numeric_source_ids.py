"""Regression: cited ticket IDs must not become numeric product claims."""

import json

import pytest

from sprint2docs import import_file
from sprint2docs.claim_validator import validate_claim
from sprint2docs.generation_models import DraftClaim, Evidence


def check(text, cited_id="FLEET-142"):
    result = import_file(
        json.dumps(
            {
                "schema_version": "1.0",
                "artifact_type": "ticket",
                "records": [
                    {
                        "id": "FLEET-142",
                        "title": "Administrator MFA",
                        "description": "Adds TOTP enrollment for administrators.",
                    }
                ],
            }
        ).encode(),
        "tickets.json",
    )
    source = result.artifacts[0]
    claim = DraftClaim(
        audience="technical",
        category="New Feature",
        text=text,
        evidence=(
            Evidence(
                artifact_key=source.artifact_key,
                artifact_id=cited_id,
                field="description",
                excerpt="Adds TOTP enrollment for administrators.",
            ),
        ),
    )
    return validate_claim(claim, result.artifacts)


@pytest.mark.parametrize(
    "text",
    [
        "Adds TOTP enrollment for administrators via FLEET-142.",
        "FLEET-142: adds TOTP enrollment for administrators.",
        "Adds administrator enrollment (FLEET-142).",
    ],
)
def test_cited_identifier_is_not_an_unsupported_quantity(text):
    result = check(text)
    assert result.status == "requires_editorial_verification"
    assert result.review_status == "pending"
    assert not result.issues


@pytest.mark.parametrize(
    "text",
    [
        "FLEET-142 adds support for 100 administrators.",
        "FLEET-142 improves performance by 142%.",
        "Adds enrollment via FLEET-1420.",
        "Adds enrollment via FLEET-142.5.",
        "Adds enrollment via OTHER-142.",
    ],
)
def test_source_id_exemption_does_not_hide_invented_numbers(text):
    result = check(text)
    assert result.status == "unsupported"
    assert "unmatched_numeric_detail" in result.issues


def test_invalid_citation_cannot_exempt_its_identifier():
    result = check("Adds enrollment via OTHER-142.", cited_id="OTHER-142")
    assert "source_identifier_mismatch" in result.issues
    assert "unmatched_numeric_detail" in result.issues
