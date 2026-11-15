from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

from app.domain.models import InvestmentAnalysisRequest
from app.services.errors import ExternalServiceError
from app.services.step_functions import execution_status, start_execution
from app.workflow.agent_runtime import (
    invoke_explainability_agent,
    invoke_named_agent,
    invoke_routed_agent,
)
from app.workflow.coordinator import (
    aggregate,
    finalize,
    finalize_clarification,
    prepare,
    research_unavailable,
)
from app.workflow.routing import (
    record_tool_failure,
    synthesize_account,
    synthesize_strategy,
    validate_account_route,
    validate_global_route,
    validate_strategy_route,
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
                    "stateEnteredEventDetails": {"name": "Global AI Orchestrator"},
                },
                {
                    "id": 2,
                    "type": "TaskStateExited",
                    "timestamp": now,
                    "stateExitedEventDetails": {"name": "Global AI Orchestrator"},
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
    assert status.events[0].agent == "Global AI Orchestrator"


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


def test_state_machine_routes_only_validated_dynamic_accounts_agents_and_tools() -> None:
    definition = json.loads(
        (ROOT / "infra" / "workflows" / "investment_analysis.asl.json").read_text()
    )
    states = definition["States"]
    accounts = states["Route Selected Accounts"]
    assert accounts["Type"] == "Map"
    assert accounts["ItemsPath"] == "$.routing.account_routes"
    account_states = accounts["ItemProcessor"]["States"]
    assert account_states["Invoke Selected Account Orchestrator"]["Parameters"]["role.$"] == "$.account_route.account_agent"
    strategies = account_states["Route Selected Specialized Agents"]
    assert strategies["Type"] == "Map"
    assert strategies["ItemsPath"] == "$.strategy_plan.strategy_routes"
    strategy_states = strategies["ItemProcessor"]["States"]
    assert strategy_states["Invoke Selected Specialized Agent"]["Parameters"]["role.$"] == "$.strategy_route.agent"
    tools = strategy_states["Route Selected Authorized Tools"]
    assert tools["Type"] == "Map"
    assert tools["ItemsPath"] == "$.tool_plan.tool_routes"
    tool_states = tools["ItemProcessor"]["States"]
    choices = tool_states["Select Authorized Tool Dispatcher"]["Choices"]
    assert {item["StringEquals"] for item in choices} == {
        "analyze_holdings_exposure",
        "market_snapshot",
        "simulate_account_purchase",
        "research_news",
    }
    assert tool_states["Invoke Authorized Financial Tool"]["Parameters"]["operation.$"] == "$.tool_route.operation"
    assert "Resource.$" not in json.dumps(definition)


def _prepared(question: str = "I am buying $5,000 CAD of NVIDIA. Evaluate suitability.") -> dict:
    return prepare(
        {
            "request_id": "2f41ce18-57d5-4921-a4d1-796c68187444",
            "request": InvestmentAnalysisRequest(question=question).model_dump(mode="json"),
        }
    )


def _agent(
    monkeypatch,
    prepared: dict,
    role: str,
    *,
    parent_id: str,
    activated: list[str] | None = None,
    operations: list[str] | None = None,
) -> dict:
    monkeypatch.setenv("BEDROCK_MODEL_ID", "us.amazon.nova-lite-v1:0")
    return invoke_named_agent(
        role,
        prepared["context"],
        request_id=prepared["context"]["request_id"],
        parent_id=parent_id,
        bedrock_client=FakeBedrock(
            {
                "summary": f"Completed qualitative {role.replace('_', ' ')} routing review.",
                "activated_agents": activated or [],
                "requested_operations": operations or [],
            }
        ),
    )


def _global_routing(monkeypatch, prepared: dict, selected: list[str]) -> dict:
    global_agent = _agent(
        monkeypatch,
        prepared,
        "global_orchestrator",
        parent_id="orchestrator.intent",
        activated=selected,
    )
    return validate_global_route(
        {
            "context": prepared["context"],
            "global_agent": global_agent,
            "trace": prepared["trace"],
        }
    )


def test_global_model_selection_changes_actual_account_map_items(monkeypatch) -> None:
    prepared = _prepared()
    tfsa = _global_routing(monkeypatch, prepared, ["tfsa_account_agent"])
    rrsp = _global_routing(monkeypatch, prepared, ["rrsp_account_agent"])

    assert [item["account_type"] for item in tfsa["account_routes"]] == ["TFSA"]
    assert [item["account_type"] for item in rrsp["account_routes"]] == ["RRSP"]
    assert next(
        item for item in tfsa["delegations"] if item["target"] == "rrsp_account_agent"
    )["actual_invocation_status"] == "not_invoked"


def test_global_route_rejects_model_account_outside_explicit_user_scope(monkeypatch) -> None:
    prepared = _prepared("I am buying $5,000 CAD of NVIDIA in my TFSA.")
    global_agent = _agent(
        monkeypatch,
        prepared,
        "global_orchestrator",
        parent_id="orchestrator.intent",
        activated=["rrsp_account_agent"],
    )
    with pytest.raises(ValueError, match="outside the validated scope"):
        validate_global_route(
            {"context": prepared["context"], "global_agent": global_agent}
        )


def test_global_question_scope_is_enforced_and_traced_as_policy(monkeypatch) -> None:
    prepared = _prepared(
        "I am buying $5,000 CAD of NVIDIA across my TFSA and RRSP."
    )
    routing = _global_routing(monkeypatch, prepared, ["tfsa_account_agent"])

    assert [route["account_type"] for route in routing["account_routes"]] == [
        "TFSA",
        "RRSP",
    ]
    rrsp = next(
        record
        for record in routing["delegations"]
        if record["target"] == "rrsp_account_agent"
    )
    assert rrsp["selected"] is True
    assert rrsp["decision_source"] == "mandatory_policy"
    assert rrsp["actual_invocation_status"] == "selected"


def test_account_model_selection_skips_nonselected_agents_and_policy_fills_safety_gap(monkeypatch) -> None:
    prepared = _prepared()
    tfsa_route = _global_routing(
        monkeypatch, prepared, ["tfsa_account_agent"]
    )["account_routes"][0]
    tfsa_agent = _agent(
        monkeypatch,
        prepared,
        "tfsa_account_agent",
        parent_id="agent.global_orchestrator",
        activated=["growth_strategy_agent"],
    )
    tfsa_plan = validate_account_route(
        {
            "context": prepared["context"],
            "account_route": tfsa_route,
            "account_agent": tfsa_agent,
        }
    )
    invoked = [item["agent"] for item in tfsa_plan["strategy_routes"]]
    assert invoked == ["growth_strategy_agent"]
    assert "momentum_strategy_agent" not in invoked

    rrsp_route = _global_routing(
        monkeypatch, prepared, ["rrsp_account_agent"]
    )["account_routes"][0]
    rrsp_agent = _agent(
        monkeypatch,
        prepared,
        "rrsp_account_agent",
        parent_id="agent.global_orchestrator",
        activated=["dividend_strategy_agent"],
    )
    rrsp_plan = validate_account_route(
        {
            "context": prepared["context"],
            "account_route": rrsp_route,
            "account_agent": rrsp_agent,
        }
    )
    assert [item["agent"] for item in rrsp_plan["strategy_routes"]] == [
        "dividend_strategy_agent",
        "capital_preservation_strategy_agent",
    ]
    preservation = next(
        item
        for item in rrsp_plan["delegations"]
        if item["target"] == "capital_preservation_strategy_agent"
    )
    assert preservation["decision_source"] == "mandatory_policy"


def test_account_route_rejects_unauthorized_specialist_selection(monkeypatch) -> None:
    prepared = _prepared()
    route = _global_routing(
        monkeypatch, prepared, ["tfsa_account_agent"]
    )["account_routes"][0]
    account_agent = _agent(
        monkeypatch,
        prepared,
        "tfsa_account_agent",
        parent_id="agent.global_orchestrator",
        activated=["growth_strategy_agent"],
    )
    account_agent["activated_agents"] = ["dividend_strategy_agent"]

    with pytest.raises(ValueError, match="unauthorized specialized agent"):
        validate_account_route(
            {
                "context": prepared["context"],
                "account_route": route,
                "account_agent": account_agent,
            }
        )


def test_strategy_model_selection_skips_nonselected_tools_and_policy_enforces_required_tools(monkeypatch) -> None:
    prepared = _prepared()
    momentum_route = {
        "agent": "momentum_strategy_agent",
        "account_id": "tfsa-demo-001",
        "account_type": "TFSA",
        "mandatory_operations": [],
        "parent_event_id": "agent.tfsa_account_agent",
    }
    momentum = _agent(
        monkeypatch,
        prepared,
        "momentum_strategy_agent",
        parent_id="agent.tfsa_account_agent",
        operations=["market_snapshot"],
    )
    optional_plan = validate_strategy_route(
        {
            "context": prepared["context"],
            "strategy_route": momentum_route,
            "strategy_agent": momentum,
        }
    )
    assert [item["operation"] for item in optional_plan["tool_routes"]] == [
        "market_snapshot"
    ]
    assert next(
        item for item in optional_plan["delegations"] if item["target"] == "research_news"
    )["actual_invocation_status"] == "not_invoked"

    growth_route = {
        "agent": "growth_strategy_agent",
        "account_id": "tfsa-demo-001",
        "account_type": "TFSA",
        "mandatory_operations": [
            "analyze_holdings_exposure",
            "simulate_account_purchase",
        ],
        "parent_event_id": "agent.tfsa_account_agent",
    }
    growth = _agent(
        monkeypatch,
        prepared,
        "growth_strategy_agent",
        parent_id="agent.tfsa_account_agent",
        operations=[],
    )
    safety_plan = validate_strategy_route(
        {
            "context": prepared["context"],
            "strategy_route": growth_route,
            "strategy_agent": growth,
        }
    )
    assert {item["operation"] for item in safety_plan["tool_routes"]} == {
        "analyze_holdings_exposure",
        "simulate_account_purchase",
    }
    assert all(
        item["decision_source"] == "mandatory_policy"
        for item in safety_plan["delegations"]
        if item["selected"]
    )


def test_strategy_route_rejects_unauthorized_tool_selection(monkeypatch) -> None:
    prepared = _prepared()
    route = {
        "agent": "dividend_strategy_agent",
        "account_id": "rrsp-demo-001",
        "account_type": "RRSP",
        "mandatory_operations": ["analyze_holdings_exposure"],
        "parent_event_id": "agent.rrsp_account_agent",
    }
    strategy_agent = _agent(
        monkeypatch,
        prepared,
        "dividend_strategy_agent",
        parent_id="agent.rrsp_account_agent",
        operations=["analyze_holdings_exposure"],
    )
    strategy_agent["requested_operations"] = ["simulate_account_purchase"]

    with pytest.raises(ValueError, match="unauthorized tool"):
        validate_strategy_route(
            {
                "context": prepared["context"],
                "strategy_route": route,
                "strategy_agent": strategy_agent,
            }
        )


def test_routed_agent_runtime_rejects_wrong_stage_and_parent(monkeypatch) -> None:
    prepared = _prepared()
    monkeypatch.setenv("BEDROCK_MODEL_ID", "us.amazon.nova-lite-v1:0")
    with pytest.raises(ValueError, match="routing stage"):
        invoke_routed_agent(
            "growth_strategy_agent",
            prepared["context"],
            routing_stage="account",
            expected_role="growth_strategy_agent",
            request_id=prepared["context"]["request_id"],
            parent_id="agent.global_orchestrator",
            bedrock_client=FakeBedrock({}),
        )
    with pytest.raises(ValueError, match="not permitted"):
        invoke_routed_agent(
            "dividend_strategy_agent",
            prepared["context"],
            routing_stage="strategy",
            expected_role="dividend_strategy_agent",
            parent_account_role="tfsa_account_agent",
            request_id=prepared["context"]["request_id"],
            parent_id="agent.tfsa_account_agent",
            bedrock_client=FakeBedrock({}),
        )


def _dataset():
    source = ROOT / "hackathon_info" / "alphaforge_starter"
    return dataset_from_csv_text(
        (source / "prices_daily.csv").read_text(),
        (source / "fx_usdcad_daily.csv").read_text(),
        sources=["s3://fixture/starter/v1/prices_daily.csv#version"],
    )


def _execute_account(monkeypatch, prepared: dict, route: dict, fail_operation: str | None = None) -> dict:
    account_selections = {
        "tfsa_account_agent": ["growth_strategy_agent", "momentum_strategy_agent"],
        "rrsp_account_agent": [
            "dividend_strategy_agent",
            "capital_preservation_strategy_agent",
        ],
    }
    operation_selections = {
        "growth_strategy_agent": [
            "analyze_holdings_exposure",
            "simulate_account_purchase",
        ],
        "momentum_strategy_agent": ["market_snapshot"],
        "dividend_strategy_agent": ["analyze_holdings_exposure"],
        "capital_preservation_strategy_agent": ["simulate_account_purchase"],
    }
    account_agent = _agent(
        monkeypatch,
        prepared,
        route["account_agent"],
        parent_id=route["parent_event_id"],
        activated=account_selections[route["account_agent"]],
    )
    plan = validate_account_route(
        {
            "context": prepared["context"],
            "account_route": route,
            "account_agent": account_agent,
        }
    )
    payload = prepared["context"]["tool_payload"]
    dataset = _dataset()
    strategy_runs = []
    for strategy_route in plan["strategy_routes"]:
        role = strategy_route["agent"]
        strategy_agent = _agent(
            monkeypatch,
            prepared,
            role,
            parent_id=strategy_route["parent_event_id"],
            operations=operation_selections[role],
        )
        tool_plan = validate_strategy_route(
            {
                "context": prepared["context"],
                "strategy_route": strategy_route,
                "strategy_agent": strategy_agent,
            }
        )
        results = []
        for tool_route in tool_plan["tool_routes"]:
            operation = tool_route["operation"]
            if operation == fail_operation:
                results.append(
                    record_tool_failure(
                        {
                            "request_id": prepared["context"]["request_id"],
                            "tool_route": tool_route,
                            "dispatch_error": {"Error": "InjectedFailure"},
                        }
                    )
                )
            elif operation == "analyze_holdings_exposure":
                results.append(analyze_holdings_exposure(payload, dataset))
            elif operation == "market_snapshot":
                results.append(market_snapshot(payload, dataset))
            elif operation == "simulate_account_purchase":
                results.append(
                    simulate_account_purchase(
                        {**payload, "account_id": route["account_id"]}, dataset
                    )
                )
            else:
                results.append(
                    research_unavailable(
                        {
                            "request_id": prepared["context"]["request_id"],
                            "ticker": "NVDA",
                            "account_id": route["account_id"],
                            "agent": role,
                            "parent_event_id": f"agent.{role}",
                        }
                    )
                )
        strategy_runs.append(
            synthesize_strategy(
                {
                    "strategy_route": strategy_route,
                    "strategy_agent": strategy_agent,
                    "tool_plan": tool_plan,
                    "tool_results": results,
                }
            )
        )
    return synthesize_account(
        {
            "context": prepared["context"],
            "account_route": route,
            "account_agent": account_agent,
            "strategy_plan": plan,
            "strategy_runs": strategy_runs,
        }
    )


def test_dynamic_workflow_completes_and_persists_actual_delegation_records(monkeypatch) -> None:
    prepared = _prepared(
        "I am buying $5,000 CAD of NVIDIA across my TFSA and RRSP."
    )
    routing = _global_routing(
        monkeypatch,
        prepared,
        ["tfsa_account_agent", "rrsp_account_agent"],
    )
    branches = [
        _execute_account(monkeypatch, prepared, route)
        for route in routing["account_routes"]
    ]
    aggregation = aggregate(
        {
            "context": prepared["context"],
            "global_agent": routing["global_agent"],
            "branches": branches,
            "delegations": routing["delegations"],
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
    assert any(record["target_kind"] == "tool" for record in result["delegations"])
    assert all(
        record["actual_invocation_status"] != "selected"
        for record in result["delegations"]
    )
    assert any(
        record["target"] == "research_news"
        and record["actual_invocation_status"] == "not_invoked"
        for record in result["delegations"]
    )


def test_failed_mandatory_tool_produces_partial_account_and_global_result(monkeypatch) -> None:
    prepared = _prepared(
        "I am buying $5,000 CAD of NVIDIA across my TFSA and RRSP."
    )
    routing = _global_routing(
        monkeypatch,
        prepared,
        ["tfsa_account_agent", "rrsp_account_agent"],
    )
    branches = []
    for route in routing["account_routes"]:
        branches.append(
            _execute_account(
                monkeypatch,
                prepared,
                route,
                fail_operation=(
                    "simulate_account_purchase"
                    if route["account_type"] == "RRSP"
                    else None
                ),
            )
        )
    rrsp = next(item for item in branches if item["branch_status"]["account_type"] == "RRSP")
    assert rrsp["branch_status"]["status"] == "partial"
    assert any(
        record["target"] == "simulate_account_purchase"
        and record["actual_invocation_status"] == "failed"
        for record in rrsp["delegations"]
    )
    aggregation = aggregate(
        {
            "context": prepared["context"],
            "global_agent": routing["global_agent"],
            "branches": branches,
            "delegations": routing["delegations"],
            "trace": prepared["trace"],
        }
    )
    assert aggregation["result_status"] == "partial"
    assert len(aggregation["account_options"]) == 1
