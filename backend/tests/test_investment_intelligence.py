from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

from app.agents.explainability import ExplainabilityAgent
from app.agents.intent import parse_investment_intent
from app.agents.orchestrator import GlobalOrchestrator
from app.domain.models import InvestmentAnalysisRequest, ResearchResult
from app.investors import etf_constituent_fixture, get_investor
from app.services.research import ResearchProvider, UnavailableResearchProvider


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "lambda" / "financial_tools"))

from calculations import (  # noqa: E402
    analyze_holdings_exposure,
    market_snapshot,
    simulate_account_purchase,
)
from data_access import dataset_from_csv_text  # noqa: E402


def _dataset():
    source = ROOT / "hackathon_info" / "alphaforge_starter"
    return dataset_from_csv_text(
        (source / "prices_daily.csv").read_text(),
        (source / "fx_usdcad_daily.csv").read_text(),
        sources=["s3://test-bucket/starter/v1/prices_daily.csv#fixture"],
    )


class RecordingFinancialTool:
    def __init__(self) -> None:
        self.dataset = _dataset()
        self.calls: list[tuple[str, str | None]] = []

    def __call__(self, operation: str, payload: dict) -> dict:
        self.calls.append((operation, payload.get("account_id")))
        functions = {
            "analyze_holdings_exposure": analyze_holdings_exposure,
            "market_snapshot": market_snapshot,
            "simulate_account_purchase": simulate_account_purchase,
        }
        return functions[operation](payload, self.dataset)


def _explainability() -> ExplainabilityAgent:
    def synthesize(packet: dict) -> dict:
        return {
            "answer": (
                "The growth account can accommodate the simulated purchase more readily, "
                "while the retirement account presents a material suitability conflict."
            ),
            "evidence_ids": packet["allowed_evidence_ids"][:3],
            "limitations": ["Historical observations do not predict future outcomes."],
            "model_id": "test-grounded-synthesizer",
        }

    return ExplainabilityAgent(synthesizer=synthesize)


def test_intent_parser_extracts_flagship_purchase_and_requests_missing_currency() -> None:
    accounts = get_investor("investor-demo-001")["accounts"]
    intent, clarification = parse_investment_intent(
        "Should I buy $5,000 CAD of NVIDIA in my TFSA or RRSP?", accounts
    )
    assert clarification is None
    assert intent is not None
    assert intent.ticker == "NVDA"
    assert intent.amount == 5000
    assert intent.currency == "CAD"
    assert intent.compare_accounts is True

    missing, clarification = parse_investment_intent("Buy $5000 of NVDA", accounts)
    assert missing is None
    assert clarification == "Is the 5,000.00 purchase amount in CAD or USD?"


def test_flagship_workflow_delegates_real_hierarchy_and_preserves_conflict() -> None:
    tool = RecordingFinancialTool()
    response = GlobalOrchestrator(
        financial_tool=tool,
        explainability_agent=_explainability(),
        research_provider=UnavailableResearchProvider(),
    ).analyze_investment(
        InvestmentAnalysisRequest(
            question=(
                "I am considering buying $5,000 CAD of NVIDIA. Which account is a "
                "better fit, my TFSA or RRSP?"
            )
        )
    )

    assert response.status == "completed"
    assert tool.calls == [
        ("analyze_holdings_exposure", None),
        ("simulate_account_purchase", "tfsa-demo-001"),
        ("market_snapshot", None),
        ("simulate_account_purchase", "rrsp-demo-001"),
    ]
    options = {option.account_type: option for option in response.account_options}
    assert options["TFSA"].compatibility in {"compatible", "conflict"}
    assert options["RRSP"].compatibility in {"caution", "conflict"}
    assert options["TFSA"].proposed_nvda_exposure > options["TFSA"].current_nvda_exposure
    assert response.current_exposure["indirect_value_cad"] > 0
    assert response.research.status == "unavailable"
    assert any(item.rule_id == "LIVE_RESEARCH_UNAVAILABLE" for item in response.governance)
    assert any(item.rule_id == "CROSS_ACCOUNT_CONFLICT" for item in response.governance)

    events = {event.event_id: event for event in response.trace}
    assert events["account.tfsa-demo-001"].parent_id == "orchestrator.intent"
    assert events["account.rrsp-demo-001"].parent_id == "orchestrator.intent"
    assert any(event.agent == "growth_strategy_agent" for event in response.trace)
    assert any(event.agent == "momentum_strategy_agent" for event in response.trace)
    assert any(event.agent == "dividend_strategy_agent" for event in response.trace)
    assert any(event.agent == "capital_preservation_strategy_agent" for event in response.trace)
    assert all(
        event.parent_id is None or event.parent_id in events
        for event in response.trace
    )
    assert all(event.ended_at >= event.started_at for event in response.trace)


def test_smaller_purchase_changes_exposure_deterministically() -> None:
    def analyze(amount: int):
        return GlobalOrchestrator(
            financial_tool=RecordingFinancialTool(),
            explainability_agent=_explainability(),
        ).analyze_investment(
            InvestmentAnalysisRequest(
                question=f"Compare buying ${amount:,} CAD of NVDA across my TFSA and RRSP."
            )
        )

    smaller = analyze(2000)
    flagship = analyze(5000)
    small_tfsa = next(item for item in smaller.account_options if item.account_type == "TFSA")
    flagship_tfsa = next(item for item in flagship.account_options if item.account_type == "TFSA")
    assert small_tfsa.proposed_nvda_exposure < flagship_tfsa.proposed_nvda_exposure
    assert small_tfsa.remaining_cash_cad > flagship_tfsa.remaining_cash_cad


def test_etf_lookthrough_fixture_is_versioned_and_source_backed() -> None:
    fixture = etf_constituent_fixture()
    assert fixture["offline_fixture"] is True
    assert fixture["fixture_version"] == "etf-lookthrough-v1"
    assert {item["publisher"] for item in fixture["holdings"]} == {
        "Invesco",
        "State Street Global Advisors",
    }
    assert all(item["url"].startswith("https://") for item in fixture["holdings"])


def test_failed_external_research_provider_is_disclosed_without_fabricated_items() -> None:
    class FailedProvider(ResearchProvider):
        def search_company(self, ticker: str) -> ResearchResult:
            return ResearchResult(
                status="failed",
                provider="test-provider",
                retrieved_at=datetime.now(timezone.utc),
                items=[],
                limitations=[f"Provider failed while retrieving {ticker}."],
            )

    response = GlobalOrchestrator(
        financial_tool=RecordingFinancialTool(),
        explainability_agent=_explainability(),
        research_provider=FailedProvider(),
    ).analyze_investment(
        InvestmentAnalysisRequest(
            question="Compare buying $2,000 CAD of NVDA across my TFSA and RRSP."
        )
    )

    assert response.research.status == "failed"
    assert response.research.items == []
    assert any(item.rule_id == "LIVE_RESEARCH_UNAVAILABLE" for item in response.governance)
    assert any(event.tool_name == "news_research" and event.status == "blocked" for event in response.trace)
