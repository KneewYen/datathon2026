"""Deterministic preparation, aggregation, and finalization for Step Functions."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.agents.governance import GovernanceAgent
from app.agents.intent import parse_investment_intent
from app.domain.models import (
    AccountOption,
    EvidenceRecord,
    ExecutionEvent,
    InvestmentAnalysisRequest,
    InvestmentAnalysisResponse,
    ResearchResult,
)
from app.investors import etf_constituent_fixture, get_investor
from app.workflow.routing import ACCOUNT_AGENT_BY_TYPE


def prepare(event: dict) -> dict:
    request_id = event["request_id"]
    request = InvestmentAnalysisRequest.model_validate(event["request"])
    fixture = get_investor(request.investor_id)
    investor = fixture["investor"]
    accounts = fixture["accounts"]
    started_at = datetime.now(timezone.utc)
    intent, clarification = parse_investment_intent(request.question, accounts)
    root_event = ExecutionEvent(
        event_id="orchestrator.intent",
        request_id=request_id,
        kind="orchestrator",
        agent="global_orchestrator",
        started_at=started_at,
        ended_at=datetime.now(timezone.utc),
        status="blocked" if clarification else "completed",
        input_summary="Parse the question and discover relevant fictional accounts.",
        output_summary=clarification or "Validated investment intent and account scope.",
    )
    if intent is None:
        return {
            "context": {
                "status": "clarification_required",
                "request_id": request_id,
                "question": request.question,
                "clarification": clarification,
                "investor": investor,
                "accounts": accounts,
            },
            "agents": {},
            "tools": {},
            "trace": [root_event.model_dump(mode="json")],
        }
    selected_accounts = [
        account
        for account in accounts
        if intent.compare_accounts or account["id"] in intent.account_ids
    ] or accounts
    selected_types = {account["type"] for account in selected_accounts}
    tool_payload = {
        "analysis_id": request_id,
        "accounts": accounts,
        "target_ticker": intent.ticker,
        "amount": intent.amount,
        "currency": intent.currency,
        "start_date": request.start_date.isoformat(),
        "end_date": request.end_date.isoformat(),
        "etf_constituents": etf_constituent_fixture(),
    }
    return {
        "context": {
            "status": "ready",
            "request_id": request_id,
            "question": request.question,
            "request": request.model_dump(mode="json"),
            "intent": intent.model_dump(mode="json"),
            "investor": investor,
            "accounts": accounts,
            "selected": {
                "TFSA": "TFSA" in selected_types,
                "RRSP": "RRSP" in selected_types,
            },
            "tool_payload": tool_payload,
        },
        "agents": {},
        "tools": {},
        "trace": [root_event.model_dump(mode="json")],
    }


def research_unavailable(event: dict) -> dict:
    started_at = datetime.now(timezone.utc)
    ticker = event["ticker"]
    result = ResearchResult(
        status="unavailable",
        provider="not-configured",
        retrieved_at=datetime.now(timezone.utc),
        items=[],
        limitations=[
            f"No approved live news provider is configured for {ticker}; no news claims were generated.",
            "The organizer dataset contains prices and macro observations, but no news feed.",
        ],
    )
    execution_event = ExecutionEvent(
        event_id=f"tool.research_news.{event.get('account_id', 'shared')}",
        parent_id=event.get("parent_event_id", "agent.momentum_strategy_agent"),
        request_id=event["request_id"],
        kind="tool",
        agent=event.get("agent", "momentum_strategy_agent"),
        tool_name="research_news",
        started_at=started_at,
        ended_at=datetime.now(timezone.utc),
        status="blocked",
        input_summary=f"Retrieve approved recent research for {ticker}.",
        output_summary="No approved live research provider is configured.",
    )
    return {
        "status": "ok",
        "operation": "research_news",
        "research": result.model_dump(mode="json"),
        "execution_event": execution_event.model_dump(mode="json"),
    }


def _branch_values(branches: list[dict]) -> tuple[dict, dict]:
    tfsa = next(
        (
            branch
            for branch in branches
            if branch.get("branch_status", {}).get("account_type") == "TFSA"
        ),
        {},
    )
    rrsp = next(
        (
            branch
            for branch in branches
            if branch.get("branch_status", {}).get("account_type") == "RRSP"
        ),
        {},
    )
    return tfsa, rrsp


def _event(value: Any) -> dict | None:
    if isinstance(value, dict):
        candidate = value.get("event") or value.get("execution_event")
        if isinstance(candidate, dict):
            return candidate
    return None


def aggregate(event: dict) -> dict:
    context = event["context"]
    tfsa, rrsp = _branch_values(event["branches"])
    branches = [branch for branch in (tfsa, rrsp) if branch]
    tools = [
        value
        for branch in branches
        for value in branch.get("tools", {}).values()
        if isinstance(value, dict)
    ]
    financial_results = [item for item in tools if item.get("status") == "ok"]
    exposure_results = [
        item
        for item in financial_results
        if item.get("operation") == "analyze_holdings_exposure"
    ]
    simulation_results = [
        item
        for item in financial_results
        if item.get("operation") == "simulate_account_purchase"
    ]
    market_results = [
        item for item in financial_results if item.get("operation") == "market_snapshot"
    ]
    if not exposure_results or not simulation_results:
        raise ValueError("account branches did not return required financial evidence")
    research_payload = next(
        (
            item["research"]
            for item in tools
            if isinstance(item.get("research"), dict)
        ),
        ResearchResult(
            status="unavailable",
            provider="not-activated",
            retrieved_at=datetime.now(timezone.utc),
            limitations=["The research tool was not activated for this account scope."],
        ).model_dump(mode="json"),
    )
    evidence_payloads = [
        evidence
        for result in [*exposure_results, *market_results, *simulation_results]
        for evidence in result.get("evidence", [])
    ]
    for item in research_payload.get("items", []):
        if item.get("evidence_id"):
            evidence_payloads.append(item)
    evidence_by_id = {item["evidence_id"]: item for item in evidence_payloads}
    evidence = [EvidenceRecord.model_validate(item) for item in evidence_by_id.values()]
    options = []
    for result in simulation_results:
        payload = dict(result["option"])
        branch = next(
            item
            for item in branches
            if item.get("branch_status", {}).get("account_type")
            == payload["account_type"]
        )
        payload["strategy_findings"] = [
            agent["finding"]
            for name, agent in branch.get("agents", {}).items()
            if name != f"{payload['account_type'].lower()}_account_agent"
            and isinstance(agent, dict)
            and isinstance(agent.get("finding"), dict)
        ]
        options.append(AccountOption.model_validate(payload))
    governance_started = datetime.now(timezone.utc)
    governance = GovernanceAgent().evaluate_investment(
        context["intent"],
        context["accounts"],
        [item.model_dump() for item in options],
        research_payload["status"],
    )
    governance_event = ExecutionEvent(
        event_id="governance.review",
        parent_id="orchestrator.intent",
        request_id=context["request_id"],
        kind="governance",
        agent="governance_agent",
        started_at=governance_started,
        ended_at=datetime.now(timezone.utc),
        status="completed",
        evidence_ids=sorted(
            {item for finding in governance for item in finding.evidence_ids}
        ),
        input_summary="Apply constraints, evidence controls, and simulation boundaries.",
        output_summary=f"Applied {len(governance)} deterministic governance findings.",
    )
    limitations = list(
        dict.fromkeys(
            [
                *[
                    item
                    for result in [
                        *exposure_results,
                        *market_results,
                        *simulation_results,
                    ]
                    for item in result.get("limitations", [])
                ],
                *research_payload.get("limitations", []),
            ]
        )
    )
    assumptions = list(
        dict.fromkeys(
            item
            for result in simulation_results
            for item in result.get("assumptions", [])
        )
    )
    trace = list(event.get("trace", []))
    global_event = _event(event.get("global_agent"))
    if global_event:
        trace.append(global_event)
    for branch in branches:
        for agent in branch.get("agents", {}).values():
            candidate = _event(agent)
            if candidate:
                trace.append(candidate)
        for value in branch.get("tools", {}).values():
            candidate = _event(value)
            if candidate:
                trace.append(candidate)
        synthesis_event = branch.get("synthesis_event")
        if isinstance(synthesis_event, dict):
            trace.append(synthesis_event)
    trace.append(governance_event.model_dump(mode="json"))
    branch_by_agent = {
        ACCOUNT_AGENT_BY_TYPE[branch["branch_status"]["account_type"]]: branch
        for branch in branches
    }
    delegations = []
    for record in event.get("delegations", []):
        updated = dict(record)
        if updated.get("selected"):
            branch = branch_by_agent.get(updated["target"])
            if branch is None:
                updated["actual_invocation_status"] = "failed"
            else:
                branch_status = branch["branch_status"].get("status")
                updated["actual_invocation_status"] = (
                    "completed"
                    if branch_status in {"completed", "partial"}
                    else "failed"
                )
                updated["evidence_ids"] = branch.get("synthesis_event", {}).get(
                    "evidence_ids", []
                )
        delegations.append(updated)
    delegations.extend(
        record for branch in branches for record in branch.get("delegations", [])
    )
    incomplete = [
        branch
        for branch in branches
        if branch.get("branch_status", {}).get("status") != "completed"
    ]
    if incomplete:
        limitations.append(
            "One or more selected account routes did not return all mandatory evidence; "
            "the response includes only completed deterministic results."
        )
    return {
        "request_id": context["request_id"],
        "question": context["question"],
        "intent": context["intent"],
        "investor": context["investor"],
        "accounts": context["accounts"],
        "current_exposure": exposure_results[0]["portfolio"],
        "account_options": [item.model_dump(mode="json") for item in options],
        "governance": [item.model_dump(mode="json") for item in governance],
        "research": research_payload,
        "evidence": [item.model_dump(mode="json") for item in evidence],
        "trace": trace,
        "delegations": delegations,
        "assumptions": assumptions,
        "limitations": limitations,
        "result_status": "partial" if incomplete else "completed",
    }


def finalize(event: dict) -> dict:
    aggregation = event["aggregation"]
    explanation = event["explanation"]["explanation"]
    trace = [*aggregation["trace"], event["explanation"]["event"]]
    response_fields = {
        key: value
        for key, value in aggregation.items()
        if key not in {"trace", "limitations", "result_status"}
    }
    response = InvestmentAnalysisResponse(
        status=aggregation.get("result_status", "completed"),
        **response_fields,
        trace=trace,
        answer=explanation["answer"],
        limitations=[
            *aggregation["limitations"],
            *explanation.get("limitations", []),
        ],
        model_id=explanation["model_id"],
    )
    return response.model_dump(mode="json")


def finalize_clarification(event: dict) -> dict:
    context = event["context"]
    result = InvestmentAnalysisResponse(
        request_id=context["request_id"],
        status="clarification_required",
        question=context["question"],
        clarification=context["clarification"],
        investor=context["investor"],
        accounts=context["accounts"],
        research=ResearchResult(
            status="unavailable",
            provider="not-invoked",
            retrieved_at=datetime.now(timezone.utc),
            limitations=[
                "Research was not attempted because the investment request needs clarification."
            ],
        ),
        trace=event["trace"],
        answer=context["clarification"],
        model_id="not-invoked",
    )
    return result.model_dump(mode="json")
