"""AWS Lambda entry points used by the investment state machine."""

from __future__ import annotations

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
    record_account_failure,
    record_strategy_failure,
    record_tool_failure,
    synthesize_account,
    synthesize_strategy,
    validate_account_route,
    validate_global_route,
    validate_strategy_route,
)


def agent_handler(event, _context):
    role = event["role"]
    if role == "explainability_agent":
        return invoke_explainability_agent(event["aggregation"])
    if event.get("routing_stage"):
        return invoke_routed_agent(
            role,
            event["context"],
            routing_stage=event["routing_stage"],
            expected_role=event["expected_role"],
            request_id=event["request_id"],
            parent_id=event["parent_id"],
            parent_account_role=event.get("parent_account_role"),
        )
    return invoke_named_agent(
        role,
        event["context"],
        request_id=event["request_id"],
        parent_id=event["parent_id"],
    )


def coordinator_handler(event, _context):
    operations = {
        "prepare": prepare,
        "research_unavailable": research_unavailable,
        "aggregate": aggregate,
        "finalize": finalize,
        "finalize_clarification": finalize_clarification,
        "validate_global_route": validate_global_route,
        "validate_account_route": validate_account_route,
        "validate_strategy_route": validate_strategy_route,
        "synthesize_strategy": synthesize_strategy,
        "synthesize_account": synthesize_account,
        "record_tool_failure": record_tool_failure,
        "record_strategy_failure": record_strategy_failure,
        "record_account_failure": record_account_failure,
    }
    operation = event.get("operation")
    handler = operations.get(operation)
    if handler is None:
        raise ValueError(f"unsupported coordinator operation: {operation}")
    return handler(event)
