from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app
from app.services.errors import ExternalServiceError


def test_health_contract() -> None:
    response = TestClient(app).get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "portfolioguard-api"}


def test_analysis_validation_rejects_invalid_weight_total() -> None:
    response = TestClient(app).post(
        "/api/analysis",
        json={
            "persona_id": "amira",
            "account_type": "TFSA",
            "strategy_allocations": {
                "growth": 0.6,
                "dividend": 0.2,
                "momentum": 0.1,
                "preservation": 0.2,
            },
            "shift": {
                "from_strategy": "growth",
                "to_strategy": "dividend",
                "amount": 0.2,
            },
            "start_date": "2023-11-13",
            "end_date": "2026-11-12",
        },
    )
    assert response.status_code == 422
    assert "strategy weights must sum to 1" in response.text


def test_analysis_fails_closed_when_aws_is_not_configured(monkeypatch) -> None:
    monkeypatch.delenv("AWS_REGION", raising=False)
    monkeypatch.delenv("LAMBDA_FUNCTION_NAME", raising=False)

    response = TestClient(app).post("/api/analysis", json={})

    assert response.status_code == 503
    assert "AWS_REGION and LAMBDA_FUNCTION_NAME are required" in response.text


def test_analysis_maps_live_aws_failure_to_bad_gateway(monkeypatch) -> None:
    def fail(_request):
        raise ExternalServiceError("financial Lambda failed: unavailable")

    monkeypatch.setattr("app.api.chat.orchestrator.run", fail)

    response = TestClient(app).post("/api/analysis", json={})

    assert response.status_code == 502
    assert response.json()["detail"] == "financial Lambda failed: unavailable"
