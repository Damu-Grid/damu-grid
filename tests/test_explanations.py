import json
import sqlite3

import httpx
from fastapi.testclient import TestClient

from backend.app.audit import AuditStore
from backend.app.explanations import (
    ExplanationService,
    ExplanationSettings,
    OpenAICompatibleProvider,
    ProviderRateLimited,
)
from backend.app.main import create_app
from backend.app.schemas import Suggestion, Uncertainty


def make_suggestion() -> Suggestion:
    return Suggestion(
        suggestion_id="sug-test",
        as_of="2026-10-31T23:59:59+03:00",
        data_age_hours=None,
        component="RBC",
        blood_group="O+",
        unit_ids=["unit-test"],
        from_facility_id="RBTC-test",
        to_facility_id="HSP-test",
        expiry_date="2026-11-15",
        typical_travel_hours=None,
        sender_reserve_units=None,
        sender_stock_after=None,
        recipient_gap_units=None,
        uncertainty=Uncertainty(method="test", label="synthetic test"),
        reason_deterministic="Move 2 units before expiry.",
        policy="expiry_aware",
        fallback=False,
        eligibility_ok=True,
    )


def test_provider_timeout_falls_back_to_template_and_is_audited(tmp_path) -> None:
    audit_path = tmp_path / "actions.sqlite"
    audit = AuditStore(audit_path)

    def timeout(_prompt: str) -> str:
        raise httpx.ReadTimeout("provider timed out")

    service = ExplanationService(
        ExplanationSettings(enabled=True, model="test-model"), audit, provider=timeout
    )
    client = TestClient(
        create_app(
            database_path=tmp_path / "unused.sqlite",
            suggestion_provider=lambda _policy: [make_suggestion()],
            explanation_service=service,
        )
    )

    response = client.get("/suggestions")

    card = response.json()["items"][0]
    assert card["explanation_source"] == "template"
    assert card["explanation_model"] == "test-model"
    assert card["latency_ms"] >= 0
    assert card["reason_deterministic"] == "Move 2 units before expiry."
    with sqlite3.connect(audit_path) as connection:
        (raw_payload,) = connection.execute(
            "SELECT payload_json FROM audit_events WHERE event_type = 'llm_explanation'"
        ).fetchone()
    payload = json.loads(raw_payload)
    assert payload["outcome"] == "timeout"
    assert payload["provider"] == "openai-compatible"
    assert payload["model"] == "test-model"


def test_rate_limit_falls_back_to_template_and_is_audited(tmp_path) -> None:
    audit_path = tmp_path / "actions.sqlite"
    service = ExplanationService(
        ExplanationSettings(enabled=True, model="test-model"),
        AuditStore(audit_path),
        provider=lambda _prompt: (_ for _ in ()).throw(ProviderRateLimited()),
    )

    result = service.apply(make_suggestion())

    assert result.explanation_source == "template"
    assert result.reason_llm is None
    with sqlite3.connect(audit_path) as connection:
        (payload,) = connection.execute("SELECT payload_json FROM audit_events").fetchone()
    assert json.loads(payload)["outcome"] == "rate_limited"


def test_successful_explanation_metadata_is_in_response_and_audit(tmp_path) -> None:
    audit_path = tmp_path / "actions.sqlite"
    service = ExplanationService(
        ExplanationSettings(enabled=True, model="test-model"),
        AuditStore(audit_path),
        provider=lambda _prompt: "Move 2 units before expiry.",
    )
    client = TestClient(
        create_app(
            database_path=tmp_path / "unused.sqlite",
            suggestion_provider=lambda _policy: [make_suggestion()],
            explanation_service=service,
        )
    )

    card = client.get("/suggestions").json()["items"][0]

    assert card["explanation_source"] == "llm"
    assert card["explanation_model"] == "test-model"
    assert isinstance(card["latency_ms"], int)
    assert card["reason_llm"] == "Move 2 units before expiry."
    with sqlite3.connect(audit_path) as connection:
        rows = connection.execute("SELECT event_type, payload_json FROM audit_events").fetchall()
    assert len(rows) == 1
    assert rows[0][0] == "llm_explanation"
    assert json.loads(rows[0][1])["outcome"] == "success"
    assert "api_key" not in rows[0][1].lower()
    assert "prompt" not in rows[0][1].lower()


def test_unsafe_transfusion_claim_falls_back_and_is_audited(tmp_path) -> None:
    audit_path = tmp_path / "actions.sqlite"
    service = ExplanationService(
        ExplanationSettings(enabled=True, model="test-model"),
        AuditStore(audit_path),
        provider=lambda _prompt: "Move 2 units before expiry; units are safe to transfuse.",
    )

    result = service.apply(make_suggestion())

    assert result.explanation_source == "template"
    assert result.reason_llm is None
    with sqlite3.connect(audit_path) as connection:
        (payload,) = connection.execute("SELECT payload_json FROM audit_events").fetchone()
    assert json.loads(payload)["outcome"] == "rejected_unsafe_claim"


def test_audit_failure_does_not_fail_suggestions_response(tmp_path, caplog) -> None:
    class BrokenAudit:
        def append_llm_call(self, **_kwargs) -> None:
            raise sqlite3.OperationalError("audit store unavailable")

    service = ExplanationService(
        ExplanationSettings(enabled=True, model="test-model"),
        BrokenAudit(),
        provider=lambda prompt: prompt,
    )
    client = TestClient(
        create_app(
            database_path=tmp_path / "unused.sqlite",
            suggestion_provider=lambda _policy: [make_suggestion()],
            explanation_service=service,
        )
    )

    response = client.get("/suggestions")

    assert response.status_code == 200
    assert response.json()["items"][0]["explanation_source"] == "llm"
    assert "Failed to append LLM audit entry" in caplog.text


def test_blank_llm_environment_values_use_defaults(monkeypatch) -> None:
    monkeypatch.setenv("LLM_PROVIDER", "")
    monkeypatch.setenv("LLM_MODEL", "")
    monkeypatch.setenv("LLM_BASE_URL", "")

    settings = ExplanationSettings.from_environment()

    assert settings.provider == "openai-compatible"
    assert settings.model is None
    assert settings.base_url == "https://api.openai.com/v1"


def test_suggestions_cache_explanations_by_suggestion_and_version(tmp_path) -> None:
    calls = []
    service = ExplanationService(
        ExplanationSettings(enabled=True, model="test-model"),
        AuditStore(tmp_path / "actions.sqlite"),
        provider=lambda prompt: calls.append(prompt) or prompt,
    )
    client = TestClient(
        create_app(
            database_path=tmp_path / "unused.sqlite",
            suggestion_provider=lambda _policy: [make_suggestion()],
            explanation_service=service,
        )
    )

    first = client.get("/suggestions").json()["items"][0]
    repeated = client.get("/suggestions").json()["items"][0]

    assert first["explanation_source"] == repeated["explanation_source"] == "llm"
    assert len(calls) == 1
    with sqlite3.connect(tmp_path / "actions.sqlite") as connection:
        connection.execute("UPDATE unit_state SET version = 1 WHERE unit_id = 'unit-test'")

    changed_version = client.get("/suggestions").json()["items"][0]

    assert changed_version["unit_version"] == 1
    assert changed_version["explanation_source"] == "llm"
    assert len(calls) == 2


def test_suggestions_explanation_pass_uses_one_eight_second_budget(tmp_path) -> None:
    clock_now = [0.0]
    calls = []

    def provider(prompt: str) -> str:
        calls.append(prompt)
        clock_now[0] += 8.1
        return prompt

    service = ExplanationService(
        ExplanationSettings(enabled=True, model="test-model"),
        AuditStore(tmp_path / "actions.sqlite"),
        provider=provider,
        clock=lambda: clock_now[0],
    )
    first = make_suggestion()
    second = first.model_copy(
        update={"suggestion_id": "sug-second", "unit_ids": ["unit-second"]}
    )
    client = TestClient(
        create_app(
            database_path=tmp_path / "unused.sqlite",
            suggestion_provider=lambda _policy: [first, second],
            explanation_service=service,
        )
    )

    results = client.get("/suggestions").json()["items"]

    assert [result["explanation_source"] for result in results] == ["llm", "template"]
    assert results[1]["reason_llm"] is None
    assert len(calls) == 1


def test_numeric_mismatch_uses_template_fallback(tmp_path) -> None:
    service = ExplanationService(
        ExplanationSettings(enabled=True, model="test-model"),
        AuditStore(tmp_path / "actions.sqlite"),
        provider=lambda _prompt: "Move 3 units before expiry.",
    )

    result = service.apply(make_suggestion())

    assert result.explanation_source == "template"
    assert result.reason_llm is None


def test_http_429_is_classified_as_rate_limited(tmp_path) -> None:
    audit_path = tmp_path / "actions.sqlite"
    service = ExplanationService(
        ExplanationSettings(enabled=True, model="test-model"),
        AuditStore(audit_path),
        provider=lambda _prompt: (_ for _ in ()).throw(
            httpx.HTTPStatusError(
                "rate limited",
                request=httpx.Request("POST", "https://provider.invalid"),
                response=httpx.Response(429),
            )
        ),
    )

    result = service.apply(make_suggestion())

    assert result.explanation_source == "template"
    with sqlite3.connect(audit_path) as connection:
        (payload,) = connection.execute("SELECT payload_json FROM audit_events").fetchone()
    assert json.loads(payload)["outcome"] == "rate_limited"


def test_live_provider_http_request_uses_five_second_timeout(monkeypatch) -> None:
    observed = {}

    class Response:
        status_code = 200

        @staticmethod
        def raise_for_status() -> None:
            return None

        @staticmethod
        def json() -> dict:
            return {"choices": [{"message": {"content": "Move 2 units before expiry."}}]}

    def fake_post(url, **kwargs):
        observed["url"] = url
        observed.update(kwargs)
        return Response()

    monkeypatch.setattr(httpx, "post", fake_post)
    provider = OpenAICompatibleProvider(
        ExplanationSettings(enabled=True, model="test-model", api_key="test-key")
    )

    result = provider.rewrite("Move 2 units before expiry.")

    assert result == "Move 2 units before expiry."
    assert observed["timeout"] == 5.0
    assert "Authorization" in observed["headers"]
