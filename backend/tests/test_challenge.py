from __future__ import annotations

import sys
from pathlib import Path

import pytest

from app.agents.challenge import parse_request
from app.agents.explainability import ExplainabilityAgent
from app.agents.governance import profile_controls
from app.agents.orchestrator import GlobalOrchestrator
from app.domain.models import AnalysisRequest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "lambda" / "financial_tools"))

import calculations  # noqa: E402
from data_access import dataset_from_csv_text  # noqa: E402


@pytest.fixture(scope="module")
def orchestrator() -> GlobalOrchestrator:
    source = ROOT / "hackathon_info" / "alphaforge_starter"
    dataset = dataset_from_csv_text(
        (source / "prices_daily.csv").read_text(),
        (source / "fx_usdcad_daily.csv").read_text(),
        sources=["fixture"],
    )

    def financial_tool(operation: str, payload: dict) -> dict:
        return {**getattr(calculations, operation)(payload, dataset), "aws_request_id": "fixture"}

    def synthesizer(packet: dict) -> dict:
        assert "allowed_tokens" not in packet
        return {
            "answer": "Grounded answer without digits.",
            "evidence_ids": packet["allowed_evidence_ids"][:1],
            "limitations": [],
            "model_id": "fixture-model",
        }

    return GlobalOrchestrator(financial_tool, ExplainabilityAgent(synthesizer))


@pytest.mark.parametrize(
    "message, ticker, weight, source",
    [
        ("Put 25% of my RRSP in NVDA", "NVDA", 0.25, "stated"),
        ("Should I buy Tesla now?", "TSLA", 0.10, "assumed"),
        ("Add $45k of bitcoin", "BTC-USD", 0.10, "stated_amount"),
    ],
)
def test_request_parser_extracts_asset_and_size(message, ticker, weight, source) -> None:
    parsed = parse_request(message, portfolio_value=450_000)
    assert parsed["ticker"] == ticker
    assert parsed["weight"] == pytest.approx(weight)
    assert parsed["weight_source"] == source


def test_request_parser_ignores_text_without_a_known_asset() -> None:
    assert parse_request("Is the market expensive?", portfolio_value=100_000) is None


def test_same_stock_request_adapts_to_each_persona(orchestrator) -> None:
    robert = orchestrator.challenge("robert", "Put 25% of my RRSP in NVDA")
    requested = next(item for item in robert.scenarios if item.id == "requested")
    assert {f.rule_id for f in requested.findings} >= {"SINGLE_POSITION_CAP", "STRESS_BUDGET_EXCEEDED"}
    assert robert.verdict == "cap"
    assert any(g.rule_id == "REQUEST_CONFLICTS_WITH_PROFILE" for g in robert.governance)

    amira = orchestrator.challenge("amira", "Should I buy Tesla?")
    assert amira.verdict == "aligned"


def test_esg_excluded_asset_gets_no_capped_version(orchestrator) -> None:
    mateo = orchestrator.challenge("mateo", "Put 10% in Exxon")
    ids = [item.id for item in mateo.scenarios]
    assert "capped" not in ids
    requested = next(item for item in mateo.scenarios if item.id == "requested")
    assert "ESG_EXCLUSION_CONFLICT" in {f.rule_id for f in requested.findings}
    assert mateo.verdict == "alternative"


def test_challenge_answer_numbers_come_from_the_evidence_registry(orchestrator) -> None:
    response = orchestrator.challenge("robert", "Put 25% of my RRSP in NVDA")
    evidence = [segment for segment in response.answer_segments if segment["type"] == "evidence"]
    tokens = {segment["token"] for segment in evidence}
    assert {"scenario.requested.stress_2022_drawdown", "scenario.capped.stress_2022_drawdown"} <= tokens
    for segment in evidence:
        assert segment["text"] == response.evidence[segment["token"]]["display"]
    assert response.answer.startswith("Grounded answer without digits.")


def test_persona_scenarios_produce_different_conclusions(orchestrator) -> None:
    amira = orchestrator.run(AnalysisRequest.for_persona("amira"))
    robert = orchestrator.run(AnalysisRequest.for_persona("robert"))
    assert amira.conclusion == "risk_reduced"
    assert robert.conclusion == "risk_increased"
    assert robert.robustness["consistent"] is True
    assert "metric.stress_2022_drawdown.proposed" in robert.evidence


@pytest.mark.parametrize(
    "persona, weights, rule",
    [
        ("amira", {"BTC-USD": 0.2, "SPY": 0.8}, "CRYPTO_CAP_EXCEEDED"),
        ("robert", {"BTC-USD": 0.05, "SPY": 0.95}, "CRYPTO_OUTSIDE_PROFILE"),
        ("mateo", {"ENB.TO": 0.1, "ESGV": 0.9}, "ESG_EXCLUSION_CONFLICT"),
    ],
)
def test_profile_controls_apply_persona_budget(persona, weights, rule) -> None:
    findings = profile_controls(persona, weights, None, None, {})
    assert rule in {finding.rule_id for finding in findings}
