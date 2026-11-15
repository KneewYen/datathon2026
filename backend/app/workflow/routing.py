"""Validated dynamic routing and delegation records for the AWS workflow.

Model output is treated as untrusted data. These gates convert named selections into
bounded route objects; Step Functions can iterate those objects but never receives a
model-provided Lambda ARN or arbitrary operation name.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.domain.models import DelegationRecord, ExecutionEvent
from app.workflow.agent_runtime import AGENTS


ACCOUNT_AGENT_BY_TYPE = {
    "TFSA": "tfsa_account_agent",
    "RRSP": "rrsp_account_agent",
}
ACCOUNT_TYPE_BY_AGENT = {value: key for key, value in ACCOUNT_AGENT_BY_TYPE.items()}
REQUIRED_ACCOUNT_OPERATIONS = (
    "analyze_holdings_exposure",
    "simulate_account_purchase",
)
FINANCIAL_OPERATIONS = {
    "analyze_holdings_exposure",
    "market_snapshot",
    "simulate_account_purchase",
}
COORDINATOR_OPERATIONS = {"research_news"}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _unique_strings(value: Any, label: str) -> list[str]:
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        raise ValueError(f"{label} must be a list of capability names")
    if len(value) != len(set(value)):
        raise ValueError(f"{label} must not contain duplicates")
    return value


def _record(
    *,
    delegation_id: str,
    request_id: str,
    decision_maker: str,
    target_kind: str,
    target: str,
    selected: bool,
    decision_source: str,
    rationale: str,
    parent_event_id: str,
) -> dict:
    return DelegationRecord(
        delegation_id=delegation_id,
        request_id=request_id,
        decision_maker=decision_maker,
        target_kind=target_kind,
        target=target,
        selected=selected,
        decision_source=decision_source,
        rationale=rationale,
        parent_event_id=parent_event_id,
        actual_invocation_status="selected" if selected else "not_invoked",
    ).model_dump(mode="json")


def validate_global_route(event: dict) -> dict:
    context = event["context"]
    result = event["global_agent"]
    if result.get("role") != "global_orchestrator":
        raise ValueError("global routing requires the global_orchestrator result")
    request_id = context["request_id"]
    accounts = context["accounts"]
    candidate_types = {
        account["type"] for account in accounts if context["selected"].get(account["type"])
    }
    candidate_agents = [
        ACCOUNT_AGENT_BY_TYPE[account_type]
        for account_type in ACCOUNT_AGENT_BY_TYPE
        if account_type in candidate_types
    ]
    selected = _unique_strings(result.get("activated_agents"), "activated_agents")
    unsupported = set(selected) - set(candidate_agents)
    if unsupported:
        raise ValueError("global orchestrator selected an account outside the validated scope")

    intent = context["intent"]
    policy_required = set(candidate_agents) if (
        intent.get("compare_accounts") or intent.get("account_ids")
    ) else set()
    if not selected and not policy_required:
        raise ValueError("global orchestrator must select at least one candidate account")
    active = set(selected) | policy_required
    rationale = result["finding"]["summary"]
    records = []
    routes = []
    for account_agent in candidate_agents:
        account_type = ACCOUNT_TYPE_BY_AGENT[account_agent]
        account = next(item for item in accounts if item["type"] == account_type)
        model_selected = account_agent in selected
        enforced = account_agent in policy_required and not model_selected
        is_selected = account_agent in active
        source = "mandatory_policy" if enforced else "model"
        record_id = f"delegation.global.{account_agent}"
        record_rationale = (
            f"User-requested account scope requires {account_type} analysis."
            if enforced
            else rationale
        )
        records.append(
            _record(
                delegation_id=record_id,
                request_id=request_id,
                decision_maker="global_orchestrator",
                target_kind="account",
                target=account_agent,
                selected=is_selected,
                decision_source=source,
                rationale=record_rationale,
                parent_event_id="agent.global_orchestrator",
            )
        )
        if is_selected:
            routes.append(
                {
                    "delegation_id": record_id,
                    "account_id": account["id"],
                    "account_type": account_type,
                    "account_agent": account_agent,
                    "account": account,
                    "decision_source": source,
                    "rationale": record_rationale,
                    "parent_event_id": "agent.global_orchestrator",
                }
            )
    return {
        "context": context,
        "global_agent": result,
        "account_routes": routes,
        "delegations": records,
        "trace": event.get("trace", []),
    }


def validate_account_route(event: dict) -> dict:
    context = event["context"]
    route = event["account_route"]
    result = event["account_agent"]
    role = route["account_agent"]
    if result.get("role") != role or ACCOUNT_TYPE_BY_AGENT.get(role) != route["account_type"]:
        raise ValueError("account agent result does not match its validated route")
    definition = AGENTS[role]
    selected = _unique_strings(result.get("activated_agents"), "activated_agents")
    if not set(selected).issubset(definition.allowed_agents):
        raise ValueError("account agent selected an unauthorized specialized agent")

    active = list(selected)
    mandatory_by_agent: dict[str, list[str]] = {name: [] for name in definition.allowed_agents}
    for operation in REQUIRED_ACCOUNT_OPERATIONS:
        owner = next(
            (
                name
                for name in active
                if operation in AGENTS[name].allowed_operations
            ),
            None,
        )
        if owner is None:
            owner = next(
                name
                for name in definition.allowed_agents
                if operation in AGENTS[name].allowed_operations
            )
            if owner not in active:
                active.append(owner)
        mandatory_by_agent[owner].append(operation)

    records = []
    strategy_routes = []
    model_rationale = result["finding"]["summary"]
    for agent in definition.allowed_agents:
        model_selected = agent in selected
        policy_selected = agent in active and not model_selected
        is_selected = agent in active
        source = "mandatory_policy" if policy_selected else "model"
        record_id = f"delegation.{route['account_id']}.{agent}"
        rationale = (
            "Mandatory risk policy activated this specialist to cover required deterministic analysis."
            if policy_selected
            else model_rationale
        )
        records.append(
            _record(
                delegation_id=record_id,
                request_id=context["request_id"],
                decision_maker=role,
                target_kind="agent",
                target=agent,
                selected=is_selected,
                decision_source=source,
                rationale=rationale,
                parent_event_id=f"agent.{role}",
            )
        )
        if is_selected:
            strategy_routes.append(
                {
                    "delegation_id": record_id,
                    "agent": agent,
                    "account_id": route["account_id"],
                    "account_type": route["account_type"],
                    "decision_source": source,
                    "rationale": rationale,
                    "mandatory_operations": mandatory_by_agent[agent],
                    "parent_event_id": f"agent.{role}",
                }
            )
    return {
        "strategy_routes": strategy_routes,
        "delegations": records,
        "required_operations": list(REQUIRED_ACCOUNT_OPERATIONS),
    }


def validate_strategy_route(event: dict) -> dict:
    context = event["context"]
    route = event["strategy_route"]
    result = event["strategy_agent"]
    role = route["agent"]
    if result.get("role") != role:
        raise ValueError("specialized agent result does not match its validated route")
    definition = AGENTS[role]
    requested = _unique_strings(result.get("requested_operations"), "requested_operations")
    mandatory = _unique_strings(route.get("mandatory_operations", []), "mandatory_operations")
    if not set(requested).issubset(definition.allowed_operations):
        raise ValueError("specialized agent selected an unauthorized tool")
    if not set(mandatory).issubset(definition.allowed_operations):
        raise ValueError("safety policy assigned a tool outside the specialist allowlist")
    active = set(requested) | set(mandatory)
    rationale = result["finding"]["summary"]
    records = []
    tool_routes = []
    for operation in definition.allowed_operations:
        model_selected = operation in requested
        policy_selected = operation in mandatory and not model_selected
        is_selected = operation in active
        source = "mandatory_policy" if policy_selected else "model"
        record_id = f"delegation.{route['account_id']}.{role}.{operation}"
        record_rationale = (
            "Mandatory risk policy requires this deterministic evidence before account synthesis."
            if policy_selected
            else rationale
        )
        records.append(
            _record(
                delegation_id=record_id,
                request_id=context["request_id"],
                decision_maker=role,
                target_kind="tool",
                target=operation,
                selected=is_selected,
                decision_source=source,
                rationale=record_rationale,
                parent_event_id=f"agent.{role}",
            )
        )
        if is_selected:
            dispatch = (
                "financial"
                if operation in FINANCIAL_OPERATIONS
                else "coordinator"
                if operation in COORDINATOR_OPERATIONS
                else None
            )
            if dispatch is None:
                raise ValueError("validated tool has no authorized dispatcher")
            tool_routes.append(
                {
                    "delegation_id": record_id,
                    "operation": operation,
                    "dispatch": dispatch,
                    "agent": role,
                    "account_id": route["account_id"],
                    "account_type": route["account_type"],
                    "decision_source": source,
                    "rationale": record_rationale,
                    "parent_event_id": f"agent.{role}",
                }
            )
    return {"tool_routes": tool_routes, "delegations": records}


def _result_event(result: Any) -> dict | None:
    if not isinstance(result, dict):
        return None
    candidate = result.get("event") or result.get("execution_event")
    return candidate if isinstance(candidate, dict) else None


def _result_operation(result: Any) -> str | None:
    if not isinstance(result, dict):
        return None
    return result.get("operation") or result.get("requested_operation")


def _updated_record(record: dict, result: dict | None) -> dict:
    updated = dict(record)
    if not updated["selected"]:
        return updated
    event = _result_event(result)
    if event:
        status = event.get("status", "failed")
        updated["actual_invocation_status"] = (
            status if status in {"completed", "blocked", "failed"} else "failed"
        )
        updated["evidence_ids"] = list(event.get("evidence_ids", []))
    elif isinstance(result, dict) and result.get("status") == "ok":
        updated["actual_invocation_status"] = "completed"
        updated["evidence_ids"] = [
            item["evidence_id"] for item in result.get("evidence", [])
        ]
    else:
        updated["actual_invocation_status"] = "failed"
    return updated


def synthesize_strategy(event: dict) -> dict:
    route = event["strategy_route"]
    agent = event["strategy_agent"]
    plan = event["tool_plan"]
    results = event.get("tool_results", [])
    by_operation = {_result_operation(item): item for item in results}
    records = [
        _updated_record(record, by_operation.get(record["target"]))
        for record in plan["delegations"]
    ]
    mandatory = set(route.get("mandatory_operations", []))
    failed_required = [
        record["target"]
        for record in records
        if record["target"] in mandatory
        and record["actual_invocation_status"] != "completed"
    ]
    failed_optional = [
        record["target"]
        for record in records
        if record["selected"]
        and record["target"] not in mandatory
        and record["actual_invocation_status"] == "failed"
    ]
    status = "failed" if failed_required else "partial" if failed_optional else "completed"
    return {
        "role": route["agent"],
        "status": status,
        "finding": agent.get("finding"),
        "event": agent.get("event"),
        "tool_results": results,
        "delegations": records,
        "failed_required_operations": failed_required,
    }


def record_tool_failure(event: dict) -> dict:
    route = event["tool_route"]
    error_name = event.get("dispatch_error", {}).get("Error", "States.TaskFailed")
    execution_event = ExecutionEvent(
        event_id=f"tool.{route['operation']}.{route['account_id']}.failed",
        parent_id=route["parent_event_id"],
        request_id=event["request_id"],
        kind="tool",
        agent=route["agent"],
        tool_name=route["operation"],
        started_at=_now(),
        ended_at=_now(),
        status="failed",
        input_summary=f"Invoke authorized {route['operation']} route.",
        output_summary="The authorized tool did not complete; no evidence was synthesized.",
        error=error_name,
    )
    return {
        "status": "error",
        "operation": route["operation"],
        "requested_operation": route["operation"],
        "execution_event": execution_event.model_dump(mode="json"),
    }


def record_strategy_failure(event: dict) -> dict:
    route = event["strategy_route"]
    error_name = event.get("dispatch_error", {}).get("Error", "States.TaskFailed")
    execution_event = ExecutionEvent(
        event_id=f"agent.{route['agent']}.failed",
        parent_id=route["parent_event_id"],
        request_id=event["request_id"],
        kind="agent",
        agent=route["agent"],
        started_at=_now(),
        ended_at=_now(),
        status="failed",
        input_summary="Run a validated specialized-agent route.",
        output_summary="The specialized agent failed; no unverified tool route was executed.",
        error=error_name,
    )
    return {
        "role": route["agent"],
        "status": "failed",
        "finding": None,
        "event": execution_event.model_dump(mode="json"),
        "tool_results": [],
        "delegations": [],
        "failed_required_operations": route.get("mandatory_operations", []),
    }


def synthesize_account(event: dict) -> dict:
    context = event["context"]
    route = event["account_route"]
    account_agent = event["account_agent"]
    plan = event["strategy_plan"]
    strategy_runs = event.get("strategy_runs", [])
    strategy_by_role = {item.get("role"): item for item in strategy_runs}
    agent_records = []
    for record in plan["delegations"]:
        run = strategy_by_role.get(record["target"])
        updated = dict(record)
        if record["selected"]:
            if run is None:
                updated["actual_invocation_status"] = "failed"
            else:
                run_status = run.get("status")
                updated["actual_invocation_status"] = (
                    "completed" if run_status in {"completed", "partial"} else "failed"
                )
                updated["evidence_ids"] = sorted(
                    {
                        evidence_id
                        for child in run.get("delegations", [])
                        for evidence_id in child.get("evidence_ids", [])
                    }
                )
        agent_records.append(updated)
    tool_results = [
        tool
        for run in strategy_runs
        for tool in run.get("tool_results", [])
        if isinstance(tool, dict)
    ]
    completed_operations = {
        _result_operation(item)
        for item in tool_results
        if (_result_event(item) or {}).get("status") == "completed"
        or item.get("status") == "ok"
    }
    missing = set(plan["required_operations"]) - completed_operations
    status = "partial" if missing else "completed"
    synthesis_event = ExecutionEvent(
        event_id=f"synthesis.{route['account_id']}",
        parent_id=f"agent.{route['account_agent']}",
        request_id=context["request_id"],
        kind="agent",
        agent=f"{route['account_type'].lower()}_account_synthesis",
        started_at=_now(),
        ended_at=_now(),
        status="failed" if missing else "completed",
        evidence_ids=sorted(
            {
                evidence_id
                for run in strategy_runs
                for record in run.get("delegations", [])
                for evidence_id in record.get("evidence_ids", [])
            }
        ),
        input_summary="Combine only actually invoked specialist and tool results.",
        output_summary=(
            "Required deterministic evidence is incomplete."
            if missing
            else "Completed account synthesis from validated delegation results."
        ),
    )
    agents = {route["account_agent"]: account_agent}
    for run in strategy_runs:
        if run.get("role"):
            agents[run["role"]] = {
                "finding": run.get("finding"),
                "event": run.get("event"),
            }
    tools = {
        f"{item.get('operation', item.get('requested_operation', 'unknown'))}:{index}": item
        for index, item in enumerate(tool_results)
    }
    return {
        "branch_status": {
            "account_id": route["account_id"],
            "account_type": route["account_type"],
            "skipped": False,
            "status": status,
        },
        "agents": agents,
        "tools": tools,
        "delegations": [
            *agent_records,
            *[
                record
                for run in strategy_runs
                for record in run.get("delegations", [])
            ],
        ],
        "synthesis_event": synthesis_event.model_dump(mode="json"),
        "missing_required_operations": sorted(missing),
    }


def record_account_failure(event: dict) -> dict:
    route = event["account_route"]
    error_name = event.get("dispatch_error", {}).get("Error", "States.TaskFailed")
    failure_event = ExecutionEvent(
        event_id=f"agent.{route['account_agent']}.failed",
        parent_id=route["parent_event_id"],
        request_id=event["request_id"],
        kind="agent",
        agent=route["account_agent"],
        started_at=_now(),
        ended_at=_now(),
        status="failed",
        input_summary="Run a validated account-agent route.",
        output_summary="The account agent failed; no specialist route was inferred or executed.",
        error=error_name,
    )
    return {
        "branch_status": {
            "account_id": route["account_id"],
            "account_type": route["account_type"],
            "skipped": False,
            "status": "failed",
        },
        "agents": {route["account_agent"]: {"event": failure_event.model_dump(mode="json")}},
        "tools": {},
        "delegations": [],
        "synthesis_event": failure_event.model_dump(mode="json"),
        "missing_required_operations": list(REQUIRED_ACCOUNT_OPERATIONS),
    }
