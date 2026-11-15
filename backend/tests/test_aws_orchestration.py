from __future__ import annotations

import json
import sys
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path

import pytest

from app.domain.models import InvestmentAnalysisRequest
from app.services.errors import ExternalServiceError
from app.services.step_functions import execution_status, start_execution
from app.workflow.agent_runtime import invoke_explainability_agent, invoke_named_agent
from app.workflow.coordinator import (
    aggregate,
    finalize,
    finalize_clarification,
    prepare,
    research_unavailable,
)


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "lambda" / "financial_tools"))

from calculations import (  # noqa: E402
    analyze_holdings_exposure,
    market_snapshot,
    simulate_account_purchase,
)
from data_access import dataset_from_csv_text  # noqa: E402


class FakeStepFunctions:
    def __init__(self, output: str | None = None) -> None:
        self.started = None
        self.output = output

    def start_execution(self, **kwargs):
        self.started = kwargs
        return {
            "executionArn": (
                "arn:aws:states:us-east-1:010928180049:execution:"
                f"portfolioguard-workshop-investment-analysis:{kwargs['name']}"
            )
        }

    def describe_execution(self, **_kwargs):
        if self.output is None:
            return {"status": "RUNNING"}
        return {"status": "SUCCEEDED", "output": self.output}

    def get_execution_history(self, **_kwargs):
        now = datetime.now(timezone.utc)
        return {
            "events": [
                {
                    "id": 1,
                    "type": "TaskStateEntered",
                    "timestamp": now,
                    "stateEnteredEventDetails": {"name": "Global Planner Agent"},
                },
                {
                    "id": 2,
                    "type": "TaskStateExited",
                    "timestamp": now,
                    "stateExitedEventDetails": {"name": "Global Planner Agent"},
                },
            ]
        }


class FakeBedrock:
    def __init__(self, document: dict) -> None:
        self.document = document

    def converse(self, **_kwargs):
        return {
            "output": {
                "message": {"content": [{"text": json.dumps(self.document)}]}
            }
        }


def test_step_functions_client_starts_named_standard_execution(monkeypatch) -> None:
    monkeypatch.setenv(
        "INVESTMENT_STATE_MACHINE_ARN",
        "arn:aws:states:us-east-1:010928180049:stateMachine:portfolioguard-workshop-investment-analysis",
    )
    monkeypatch.setenv("AWS_REGION", "us-east-1")
    fake = FakeStepFunctions()

    response = start_execution(InvestmentAnalysisRequest(), step_functions_client=fake)

    assert response.status == "RUNNING"
    assert fake.started["stateMachineArn"].endswith(
        ":stateMachine:portfolioguard-workshop-investment-analysis"
    )
    assert json.loads(fake.started["input"])["request_id"] == response.request_id


def test_step_functions_status_uses_actual_aws_history_and_validates_result(monkeypatch) -> None:
    monkeypatch.setenv(
        "INVESTMENT_STATE_MACHINE_ARN",
        "arn:aws:states:us-east-1:010928180049:stateMachine:portfolioguard-workshop-investment-analysis",
    )
    monkeypatch.setenv("AWS_REGION", "us-east-1")
    request_id = "2f41ce18-57d5-4921-a4d1-796c68187444"
    prepared = prepare(
        {
            "request_id": request_id,
            "request": {
                "question": "Which account should I use?",
                "investor_id": "investor-demo-001",
                "start_date": "2023-11-13",
                "end_date": "2026-11-12",
            },
        }
    )
    output = finalize_clarification(prepared)

    status = execution_status(
        request_id,
        step_functions_client=FakeStepFunctions(json.dumps(output)),
    )

    assert status.status == "SUCCEEDED"
    assert status.result.status == "clarification_required"
    assert status.events[0].agent == "Global Planner Agent"


def test_named_bedrock_agent_accepts_only_allowed_capabilities(monkeypatch) -> None:
    monkeypatch.setenv("BEDROCK_MODEL_ID", "us.amazon.nova-lite-v1:0")
    result = invoke_named_agent(
        "growth_strategy_agent",
        {"question": "Review a fictional technology purchase."},
        request_id="2f41ce18-57d5-4921-a4d1-796c68187444",
        parent_id="agent.tfsa_account_agent",
        bedrock_client=FakeBedrock(
            {
                "summary": "Review growth compatibility and covered technology overlap.",
                "activated_agents": [],
                "requested_operations": [
                    "analyze_holdings_exposure",
                    "simulate_account_purchase",
                ],
            }
        ),
    )

    assert result["model_id"] == "us.amazon.nova-lite-v1:0"
    assert result["event"]["parent_id"] == "agent.tfsa_account_agent"

    with pytest.raises(ExternalServiceError, match="unsupported operation"):
        invoke_named_agent(
            "growth_strategy_agent",
            {"question": "Review a fictional technology purchase."},
            request_id="2f41ce18-57d5-4921-a4d1-796c68187444",
            parent_id="agent.tfsa_account_agent",
            bedrock_client=FakeBedrock(
                {
                    "summary": "Attempt an unsupported operation.",
                    "activated_agents": [],
                    "requested_operations": ["execute_trade"],
                }
            ),
        )


def test_state_machine_contains_real_agents_tools_and_parallel_accounts() -> None:
    definition = json.loads(
        (ROOT / "infra" / "workflows" / "investment_analysis.asl.json").read_text()
    )
    states = definition["States"]

    assert states["Analyze Accounts in Parallel"]["Type"] == "Parallel"
    text = json.dumps(definition)
    for name in (
        "Global Planner Agent",
        "TFSA Account Agent",
        "Growth Strategy Agent",
        "Momentum Strategy Agent",
        "RRSP Account Agent",
        "Dividend Strategy Agent",
        "Capital Preservation Strategy Agent",
        "TFSA Holdings Exposure Tool",
        "Market Snapshot Tool",
        "RRSP Purchase Simulation Tool",
        "Explainability Agent",
    ):
        assert name in text


def test_local_state_machine_equivalent_completes_flagship_workflow(monkeypatch) -> None:
    monkeypatch.setenv("BEDROCK_MODEL_ID", "us.amazon.nova-lite-v1:0")
    request_id = "2f41ce18-57d5-4921-a4d1-796c68187444"
    prepared = prepare(
        {
            "request_id": request_id,
            "request": InvestmentAnalysisRequest().model_dump(mode="json"),
        }
    )

    def agent(role: str, parent_id: str, activated: list[str], operations: list[str]):
        return invoke_named_agent(
            role,
            prepared["context"],
            request_id=request_id,
            parent_id=parent_id,
            bedrock_client=FakeBedrock(
                {
                    "summary": f"Completed the qualitative {role.replace('_', ' ')} review.",
                    "activated_agents": activated,
                    "requested_operations": operations,
                }
            ),
        )

    global_agent = agent(
        "global_orchestrator",
        "orchestrator.intent",
        ["tfsa_account_agent", "rrsp_account_agent"],
        [],
    )
    source = ROOT / "hackathon_info" / "alphaforge_starter"
    dataset = dataset_from_csv_text(
        (source / "prices_daily.csv").read_text(),
        (source / "fx_usdcad_daily.csv").read_text(),
        sources=["s3://fixture/starter/v1/prices_daily.csv#version"],
    )
    payload = prepared["context"]["tool_payload"]

    tfsa = deepcopy(prepared)
    tfsa["agents"].update(
        {
            "tfsa": agent(
                "tfsa_account_agent",
                "orchestrator.intent",
                ["growth_strategy_agent", "momentum_strategy_agent"],
                [],
            ),
            "growth": agent(
                "growth_strategy_agent",
                "agent.tfsa_account_agent",
                [],
                ["analyze_holdings_exposure", "simulate_account_purchase"],
            ),
            "momentum": agent(
                "momentum_strategy_agent",
                "agent.tfsa_account_agent",
                [],
                ["market_snapshot", "research_news"],
            ),
        }
    )
    tfsa["tools"].update(
        {
            "tfsa_exposure": analyze_holdings_exposure(payload, dataset),
            "market": market_snapshot(payload, dataset),
            "research": research_unavailable(
                {"request_id": request_id, "ticker": "NVDA"}
            ),
            "tfsa_simulation": simulate_account_purchase(
                {**payload, "account_id": "tfsa-demo-001"}, dataset
            ),
        }
    )
    tfsa["branch_status"] = {"account_type": "TFSA", "skipped": False}

    rrsp = deepcopy(prepared)
    rrsp["agents"].update(
        {
            "rrsp": agent(
                "rrsp_account_agent",
                "orchestrator.intent",
                [
                    "dividend_strategy_agent",
                    "capital_preservation_strategy_agent",
                ],
                [],
            ),
            "dividend": agent(
                "dividend_strategy_agent",
                "agent.rrsp_account_agent",
                [],
                ["analyze_holdings_exposure"],
            ),
            "preservation": agent(
                "capital_preservation_strategy_agent",
                "agent.rrsp_account_agent",
                [],
                ["simulate_account_purchase"],
            ),
        }
    )
    rrsp["tools"].update(
        {
            "rrsp_exposure": analyze_holdings_exposure(payload, dataset),
            "rrsp_simulation": simulate_account_purchase(
                {**payload, "account_id": "rrsp-demo-001"}, dataset
            ),
        }
    )
    rrsp["branch_status"] = {"account_type": "RRSP", "skipped": False}

    aggregation = aggregate(
        {
            "context": prepared["context"],
            "global_agent": global_agent,
            "branches": [tfsa, rrsp],
            "trace": prepared["trace"],
        }
    )
    explanation = invoke_explainability_agent(
        aggregation,
        bedrock_client=FakeBedrock(
            {
                "answer": "The growth account is more compatible while the retirement account requires caution.",
                "evidence_ids": [aggregation["evidence"][0]["evidence_id"]],
                "limitations": ["Historical observations do not predict future outcomes."],
            }
        ),
    )
    result = finalize({"aggregation": aggregation, "explanation": explanation})

    assert result["status"] == "completed"
    assert len(result["account_options"]) == 2
    assert result["model_id"] == "us.amazon.nova-lite-v1:0"
    assert any(event["agent"] == "global_orchestrator" for event in result["trace"])
    assert any(event["agent"] == "explainability_agent" for event in result["trace"])
