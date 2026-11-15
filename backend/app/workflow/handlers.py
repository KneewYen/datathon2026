"""AWS Lambda entry points used by the investment state machine."""

from __future__ import annotations

from app.workflow.agent_runtime import (
    invoke_explainability_agent,
    invoke_named_agent,
)
from app.workflow.coordinator import (
    aggregate,
    finalize,
    finalize_clarification,
    prepare,
    research_unavailable,
)


def agent_handler(event, _context):
    role = event["role"]
    if role == "explainability_agent":
        return invoke_explainability_agent(event["aggregation"])
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
    }
    operation = event.get("operation")
    handler = operations.get(operation)
    if handler is None:
        raise ValueError(f"unsupported coordinator operation: {operation}")
    return handler(event)
