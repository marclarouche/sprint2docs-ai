"""Generation grounding, failure handling, and adapter capability boundaries."""

import json
from pathlib import Path

import pytest

from sprint2docs import import_file
from sprint2docs.ai_writer import SYSTEM, generate_release
from sprint2docs.analysis import analyze
from sprint2docs.generation_models import GenerationSettings, response_schema
from sprint2docs.ollama_adapter import OllamaAdapter, OllamaError


def imported(count=1):
    return import_file(
        json.dumps(
            {
                "schema_version": "1.0",
                "artifact_type": "ticket",
                "records": [
                    {
                        "id": f"T-{i}",
                        "title": "Fix retry handling",
                        "description": "Retry behavior changed; deployment is unknown.",
                        "release_id": "1.0",
                        "change_type": "bug_fix",
                    }
                    for i in range(count)
                ],
            }
        ).encode(),
        "tickets.json",
    )


def response(source, **overrides):
    evidence = {
        "artifact_key": source.artifact_key,
        "artifact_id": source.artifact_id,
        "field": "description",
        "excerpt": source.description,
    }
    evidence.update(overrides)
    return json.dumps(
        {
            "claims": [
                {
                    "audience": "technical",
                    "category": "Bug Fix",
                    "text": "Retry behavior changed; deployment is unknown.",
                    "evidence": [evidence],
                }
            ],
            "questions": [{"question": "Has this change been deployed?", "evidence": [evidence]}],
        }
    )


class FakeAdapter:
    def __init__(self, outputs):
        self.outputs = iter(outputs)
        self.calls = []

    def models(self):
        return {"local:test": "a" * 64}

    def generate(self, system, context, settings):
        self.calls.append((system, json.loads(context), settings))
        output = next(self.outputs)
        if isinstance(output, Exception):
            raise output
        return output


def run(result, adapter, **options):
    return generate_release(
        result, analyze(result), "1.0", GenerationSettings(model="local:test", **options), adapter
    )


def test_grounded_output_and_metadata_are_pending_not_verified():
    result = imported()
    before = result.model_dump_json()
    adapter = FakeAdapter([response(result.artifacts[0])])
    draft = run(result, adapter)
    assert draft.status == "complete"
    assert draft.claims[0].status == "requires_editorial_verification"
    assert draft.claims[0].review_status == "pending"
    assert draft.claims[0].provenance == (result.artifacts[0].provenance,)
    assert draft.questions[0].status == "unresolved"
    assert draft.model_digest == "a" * 64
    assert len(draft.source_snapshot_sha256) == 64
    assert result.model_dump_json() == before
    assert type(draft).model_validate_json(draft.model_dump_json()) == draft
    assert adapter.calls[0][0].startswith(SYSTEM)
    assert "UNTRUSTED SOURCE DATA" in SYSTEM


@pytest.mark.parametrize(
    "overrides,issue",
    [
        ({"artifact_key": "invented"}, "unknown_source_key"),
        ({"artifact_id": "wrong"}, "source_identifier_mismatch"),
        ({"excerpt": "Runs 100% faster"}, "excerpt_not_in_source_field"),
    ],
)
def test_bad_evidence_is_held_and_questions_rejected(overrides, issue):
    result = imported()
    draft = run(result, FakeAdapter([response(result.artifacts[0], **overrides)]))
    assert draft.claims[0].status == "unsupported"
    assert issue in draft.claims[0].issues
    assert not draft.questions
    assert draft.status == "partial"


@pytest.mark.parametrize(
    "output",
    [
        "not json",
        '{"claims": [], "questions": [], "approved": true}',
        '{"claims": [{"audience":"customer","category":"Bug Fix","text":"Claim","evidence":[]}],"questions":[]}',
    ],
)
def test_invalid_schema_is_sanitized(output):
    draft = run(imported(), FakeAdapter([output]))
    assert draft.status == "failed" and not draft.claims
    assert "invalid structured output" in draft.diagnostics[0]
    assert output not in draft.diagnostics[0]


def test_partial_failure_and_batch_local_citations():
    result = imported(2)
    draft = run(
        result,
        FakeAdapter(
            [response(result.artifacts[0]), OllamaError("Local Ollama request timed out.")]
        ),
        batch_records=1,
    )
    assert draft.status == "partial" and len(draft.claims) == 1
    cross = run(
        result,
        FakeAdapter([response(result.artifacts[1]), response(result.artifacts[1])]),
        batch_records=1,
    )
    assert cross.claims[0].status == "unsupported"
    assert "unknown_source_key" in cross.claims[0].issues


def test_limits_missing_model_and_release_do_not_generate():
    result = imported(2)
    adapter = FakeAdapter([])
    with pytest.raises(ValueError):
        run(result, adapter, max_records=1)
    with pytest.raises(ValueError):
        generate_release(
            result, analyze(result), "missing", GenerationSettings(model="local:test"), adapter
        )
    with pytest.raises(OllamaError):
        generate_release(
            result, analyze(result), "1.0", GenerationSettings(model="absent"), adapter
        )
    assert not adapter.calls


class FakeResponse:
    status = 200

    def __init__(self, data):
        self.data = data

    def read(self, size):
        return self.data[:size]


class FakeConnection:
    response = b"{}"
    calls = []
    closed = False

    def __init__(self, host, port, timeout):
        assert host == "127.0.0.1"
        self.calls.append((host, port, timeout))

    def request(self, method, path, body, headers):
        self.calls.append((method, path, json.loads(body) if body else None))

    def getresponse(self):
        return FakeResponse(self.response)

    def close(self):
        self.closed = True


def mock_connection(monkeypatch, data):
    FakeConnection.response = data
    FakeConnection.calls = []
    monkeypatch.setattr("sprint2docs.ollama_adapter.http.client.HTTPConnection", FakeConnection)


def test_adapter_loopback_nonstreaming_schema_and_no_tools(monkeypatch):
    mock_connection(monkeypatch, b'{"done":true,"message":{"content":"{}"}}')
    adapter = OllamaAdapter()
    assert adapter.generate("system", "source", GenerationSettings(model="local:test")) == "{}"
    payload = FakeConnection.calls[1][2]
    assert payload["stream"] is False and payload["think"] is False
    assert payload["format"] == response_schema(4)
    assert "tools" not in payload
    assert payload["options"]["temperature"] == 0


@pytest.mark.parametrize(
    "name", ["model:cloud", "https://remote/model", "../model", "model\nsecret"]
)
def test_cloud_names_rejected_before_transport(name):
    with pytest.raises(OllamaError):
        OllamaAdapter().generate("system", "source", GenerationSettings(model=name))


def test_model_list_filters_remote_models(monkeypatch):
    models = [
        {"name": "local:test", "digest": "a" * 64},
        {"name": "remote:cloud", "digest": "b" * 64},
        {"name": "remote:test", "digest": "c" * 64, "remote_host": "remote"},
    ]
    mock_connection(monkeypatch, json.dumps({"models": models}).encode())
    assert OllamaAdapter().models() == {"local:test": "a" * 64}


@pytest.mark.parametrize(
    "body",
    [
        b"not json",
        b'{"done":false}',
        b'{"done":true,"done_reason":"length"}',
        b'{"done":true,"message":{"content":"{}","tool_calls":[{}]}}',
        b"x" * 256001,
    ],
)
def test_adapter_invalid_or_oversized_responses(monkeypatch, body):
    mock_connection(monkeypatch, body)
    with pytest.raises(OllamaError):
        OllamaAdapter().generate("system", "source", GenerationSettings(model="local:test"))


def test_ui_generation_and_service_failure_preserve_imports(monkeypatch):
    from streamlit.testing.v1 import AppTest

    monkeypatch.setattr(OllamaAdapter, "models", lambda self: {"local:test": "a" * 64})

    def generate(self, system, context, settings):
        source = json.loads(context)["sources"][0]
        evidence = {
            "artifact_key": source["artifact_key"],
            "artifact_id": source["artifact_id"],
            "field": "title",
            "excerpt": source["title"],
        }
        return json.dumps(
            {
                "claims": [
                    {
                        "audience": "technical",
                        "category": "Unknown",
                        "text": source["title"],
                        "evidence": [evidence],
                    }
                ],
                "questions": [],
            }
        )

    monkeypatch.setattr(OllamaAdapter, "generate", generate)
    app = AppTest.from_file(
        Path(__file__).resolve().parents[1] / "app.py", default_timeout=30
    ).run()
    app.button[0].click().run()
    next(b for b in app.button if b.label == "Find local Ollama models").click().run()
    next(b for b in app.button if b.label == "Generate release note drafts").click().run()
    assert not app.exception
    previous = app.session_state["generated_release"]
    assert previous.claims

    def fail(self, system, context, settings):
        raise OllamaError("Local Ollama is unavailable.")

    monkeypatch.setattr(OllamaAdapter, "generate", fail)
    next(b for b in app.button if b.label == "Generate release note drafts").click().run()
    assert not app.exception
    assert app.session_state["generated_release"] == previous
    assert len(app.session_state["import_result"].artifacts) == 9
    assert app.error


def test_large_source_rejected_without_silent_truncation():
    data = {
        "schema_version": "1.0",
        "artifact_type": "ticket",
        "records": [
            {"id": "LONG", "title": "Long record", "description": "x" * 3000, "release_id": "1.0"}
        ],
    }
    result = import_file(json.dumps(data).encode(), "long.json")
    adapter = FakeAdapter([])
    with pytest.raises(ValueError, match="context limit"):
        run(result, adapter, max_context_chars=2000)
    assert not adapter.calls


def test_adapter_timeouts_are_safe_and_close_connection(monkeypatch):
    class TimeoutConnection(FakeConnection):
        closed = False

        def request(self, *args, **kwargs):
            raise TimeoutError("FICTIONAL_SECRET")

        def close(self):
            TimeoutConnection.closed = True

    monkeypatch.setattr("sprint2docs.ollama_adapter.http.client.HTTPConnection", TimeoutConnection)
    with pytest.raises(OllamaError, match="timed out") as error:
        OllamaAdapter().models()
    assert "FICTIONAL_SECRET" not in str(error.value)
    assert TimeoutConnection.closed


def test_generated_numbers_without_evidence_are_held():
    result = imported()
    payload = json.loads(response(result.artifacts[0]))
    payload["claims"][0]["text"] = "Retries run 100% faster."
    draft = run(result, FakeAdapter([json.dumps(payload)]))
    assert draft.claims[0].status == "unsupported"
    assert "unmatched_numeric_detail" in draft.claims[0].issues


@pytest.mark.parametrize(
    "folder,artifact_count,inventory_count",
    [
        ("00-quick-start", 1, 0),
        ("01-routine-release", 7, 2),
        ("02-ambiguous-release", 6, 0),
        ("03-review-stress-test", 2, 0),
    ],
)
def test_realistic_upload_packs(folder, artifact_count, inventory_count):
    from sprint2docs import ImportInput, import_batch

    directory = Path("samples/local_uploads") / folder
    result = import_batch(
        [ImportInput(filename=p.name, data=p.read_bytes()) for p in sorted(directory.iterdir())]
    )
    assert not result.error_count
    assert len(result.artifacts) == artifact_count
    assert len(result.inventory) == inventory_count
    analysis = analyze(result)
    if folder == "03-review-stress-test":
        assert any(i.code == "duplicate_identifier" for i in result.issues)
        assert analysis.unresolved_references[0].reason == "missing_target"
        assert all(f.audience == "Uncertain" for f in analysis.findings)
    if folder == "02-ambiguous-release":
        assert any(r.duplicate_candidate for r in analysis.relationships)


def test_batch_progress_does_not_expose_source_contents():
    result = imported(2)
    calls = []
    adapter = FakeAdapter([response(s) for s in result.artifacts])
    generate_release(
        result,
        analyze(result),
        "1.0",
        GenerationSettings(model="local:test", batch_records=1),
        adapter,
        progress=lambda current, total: calls.append((current, total)),
    )
    assert calls == [(1, 2), (2, 2)]


def test_internal_only_source_is_held_out_of_customer_notes():
    data = {
        "schema_version": "1.0",
        "artifact_type": "ticket",
        "records": [
            {
                "id": "INTERNAL",
                "title": "Build cache",
                "description": "Internal build cache changed.",
                "release_id": "1.0",
                "labels": ["internal-only"],
            }
        ],
    }
    result = import_file(json.dumps(data).encode(), "internal.json")
    output = json.loads(response(result.artifacts[0]))
    output["claims"][0]["audience"] = "customer"
    output["claims"][0]["text"] = result.artifacts[0].description
    draft = run(result, FakeAdapter([json.dumps(output)]))
    assert draft.claims[0].status == "unsupported"
    assert "internal_source_in_customer_note" in draft.claims[0].issues


def test_multibyte_context_budget_prevents_silent_model_truncation():
    result = import_file(
        json.dumps(
            {
                "schema_version": "1.0",
                "artifact_type": "ticket",
                "records": [
                    {
                        "id": "UNICODE",
                        "title": "Long description",
                        "description": "界" * 2000,
                        "release_id": "1.0",
                    }
                ],
            }
        ).encode(),
        "unicode.json",
    )
    adapter = FakeAdapter([])
    with pytest.raises(ValueError, match="context limit"):
        run(result, adapter, num_ctx=8192, num_predict=3000)
    assert not adapter.calls


def test_empty_model_result_is_failed_instead_of_replacing_previous_draft():
    draft = run(imported(), FakeAdapter(['{"claims":[],"questions":[]}']))
    assert draft.status == "failed"
    assert not draft.claims and not draft.questions
    assert "no drafts or questions" in draft.diagnostics[0]


def test_response_schema_scales_to_source_batch():
    schema = response_schema(1)
    assert schema["properties"]["claims"]["maxItems"] == 2
    assert schema["properties"]["questions"]["maxItems"] == 1


def test_reasoning_only_response_reports_model_compatibility_without_leaking_thinking(monkeypatch):
    mock_connection(
        monkeypatch,
        json.dumps(
            {
                "done": True,
                "done_reason": "length",
                "message": {"content": "", "thinking": "FICTIONAL_PRIVATE_REASONING"},
            }
        ).encode(),
    )
    with pytest.raises(OllamaError, match="non-thinking/instruct") as error:
        OllamaAdapter().generate("system", "source", GenerationSettings(model="local:test"))
    assert "FICTIONAL_PRIVATE_REASONING" not in str(error.value)
