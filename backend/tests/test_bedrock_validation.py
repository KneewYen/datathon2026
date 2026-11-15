from __future__ import annotations

import pytest

from app.services.bedrock import _validate_result
from app.services.errors import ExternalServiceError


PACKET = {
    "allowed_evidence_ids": [
        "metric.annualized_volatility",
        "metric.maximum_drawdown",
    ]
}


def test_grounded_explanation_accepts_only_supplied_evidence_ids() -> None:
    result = _validate_result(
        {
            "answer": "Measured historical risk decreased, with future outcomes still uncertain.",
            "evidence_ids": ["metric.annualized_volatility"],
            "limitations": ["Historical observations do not predict future outcomes."],
        },
        PACKET,
        "approved-model",
    )

    assert result["model_id"] == "approved-model"


@pytest.mark.parametrize(
    "document, message",
    [
        (
            {
                "answer": "Volatility fell to 13.7 percent.",
                "evidence_ids": ["metric.annualized_volatility"],
            },
            "numeric claim",
        ),
        (
            {
                "answer": "Measured historical risk decreased.",
                "evidence_ids": ["metric.unsupported"],
            },
            "unsupported evidence",
        ),
    ],
)
def test_explanation_rejects_unsupported_claims(document: dict, message: str) -> None:
    with pytest.raises(ExternalServiceError, match=message):
        _validate_result(document, PACKET, "approved-model")


def test_explanation_flags_forecast_like_return_wording() -> None:
    with pytest.raises(ExternalServiceError, match="forecast-like"):
        _validate_result(
            {"answer": "Adding Tesla could offer higher returns.", "evidence_ids": ["metric.maximum_drawdown"]},
            PACKET,
            "approved-model",
        )


def test_explanation_allows_named_stress_window_but_no_other_digits() -> None:
    packet = {**PACKET, "allowed_literals": ["2022"]}
    accepted = _validate_result(
        {"answer": "The 2022 selloff hurt this mix more.", "evidence_ids": ["metric.maximum_drawdown"]},
        packet,
        "approved-model",
    )
    assert "2022" in accepted["answer"]
    with pytest.raises(ExternalServiceError, match="numeric claim"):
        _validate_result(
            {"answer": "The 2022 selloff cost 15 percent.", "evidence_ids": ["metric.maximum_drawdown"]},
            packet,
            "approved-model",
        )


def test_explanation_accepts_allowed_tokens_but_not_unknown_ones() -> None:
    packet = {
        **PACKET,
        "allowed_tokens": {
            "metric.maximum_drawdown.current": "Maximum drawdown",
            "metric.maximum_drawdown.proposed": "Maximum drawdown",
        },
    }
    accepted = _validate_result(
        {
            "answer": "Drawdown went from {{metric.maximum_drawdown.current}} to {{ metric.maximum_drawdown.proposed }}.",
            "evidence_ids": ["metric.maximum_drawdown"],
        },
        packet,
        "approved-model",
    )
    assert accepted["answer"] == (
        "Drawdown went from {{metric.maximum_drawdown.current}} to {{metric.maximum_drawdown.proposed}}."
    )

    with pytest.raises(ExternalServiceError, match="unsupported evidence token"):
        _validate_result(
            {"answer": "Return was {{metric.invented.value}}.", "evidence_ids": ["metric.maximum_drawdown"]},
            packet,
            "approved-model",
        )
