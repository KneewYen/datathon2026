"""Start and inspect the AWS Step Functions investment workflow."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

import boto3

from app.domain.models import (
    ExecutionEvent,
    InvestmentAnalysisRequest,
    InvestmentAnalysisResponse,
    WorkflowStartResponse,
    WorkflowStatusResponse,
)
from app.services.errors import ExternalServiceError, ServiceConfigurationError


STATE_PARENTS = {
    "Global Planner Agent": "Prepare Investment Request",
    "TFSA Account Agent": "Global Planner Agent",
    "Growth Strategy Agent": "TFSA Account Agent",
    "TFSA Holdings Exposure Tool": "Growth Strategy Agent",
    "Momentum Strategy Agent": "TFSA Account Agent",
    "Market Snapshot Tool": "Momentum Strategy Agent",
    "News Research Tool": "Momentum Strategy Agent",
    "TFSA Purchase Simulation Tool": "Growth Strategy Agent",
    "RRSP Account Agent": "Global Planner Agent",
    "Dividend Strategy Agent": "RRSP Account Agent",
    "RRSP Holdings Exposure Tool": "Dividend Strategy Agent",
    "Capital Preservation Strategy Agent": "RRSP Account Agent",
    "RRSP Purchase Simulation Tool": "Capital Preservation Strategy Agent",
    "Aggregate and Govern": "Global Planner Agent",
    "Explainability Agent": "Aggregate and Govern",
    "Finalize Evidence Response": "Explainability Agent",
}


def _configuration() -> tuple[str, str]:
    state_machine_arn = os.getenv("INVESTMENT_STATE_MACHINE_ARN")
    region = os.getenv("AWS_REGION")
    if not state_machine_arn or not region:
        raise ServiceConfigurationError(
            "AWS_REGION and INVESTMENT_STATE_MACHINE_ARN are required for AWS orchestration"
        )
    return state_machine_arn, region


def client():
    _, region = _configuration()
    return boto3.client("stepfunctions", region_name=region)


def _execution_arn(state_machine_arn: str, request_id: str) -> str:
    prefix, name = state_machine_arn.rsplit(":stateMachine:", 1)
    return f"{prefix}:execution:{name}:{request_id}"


def start_execution(
    request: InvestmentAnalysisRequest, *, step_functions_client: Any | None = None
) -> WorkflowStartResponse:
    state_machine_arn, _ = _configuration()
    request_id = str(uuid4())
    execution_input = {
        "request_id": request_id,
        "request": request.model_dump(mode="json"),
    }
    api = step_functions_client or client()
    try:
        response = api.start_execution(
            stateMachineArn=state_machine_arn,
            name=request_id,
            input=json.dumps(execution_input, separators=(",", ":")),
        )
    except Exception as exc:  # botocore exceptions vary by deployment environment.
        raise ExternalServiceError(
            f"AWS Step Functions could not start the investment workflow: {exc}"
        ) from exc
    return WorkflowStartResponse(
        request_id=request_id,
        execution_arn=response["executionArn"],
    )


def _state_name(details: dict) -> str | None:
    for key in ("stateEnteredEventDetails", "stateExitedEventDetails"):
        value = details.get(key)
        if isinstance(value, dict) and isinstance(value.get("name"), str):
            return value["name"]
    return None


def _history_events(request_id: str, history: list[dict]) -> list[ExecutionEvent]:
    entered: dict[str, dict] = {}
    events: list[ExecutionEvent] = []
    for item in history:
        event_type = item.get("type", "")
        name = _state_name(item)
        if not name:
            continue
        if event_type == "TaskStateEntered":
            entered[name] = item
            continue
        if event_type != "TaskStateExited":
            continue
        start = entered.get(name, item)
        entered.pop(name, None)
        started_at = start.get("timestamp", datetime.now(timezone.utc))
        ended_at = item.get("timestamp", started_at)
        normalized = name.lower().replace(" ", ".").replace("?", "")
        parent_name = STATE_PARENTS.get(name)
        parent_id = (
            f"aws.{parent_name.lower().replace(' ', '.').replace('?', '')}"
            if parent_name
            else None
        )
        kind = "tool" if "tool" in normalized else "agent"
        if "governance" in normalized or "aggregate" in normalized:
            kind = "governance"
        elif "final" in normalized or "explain" in normalized:
            kind = "explainability"
        elif "prepare" in normalized or "planner" in normalized:
            kind = "orchestrator"
        events.append(
            ExecutionEvent(
                event_id=f"aws.{normalized}",
                parent_id=parent_id,
                request_id=request_id,
                kind=kind,
                agent=name,
                tool_name=name if kind == "tool" else None,
                started_at=started_at,
                ended_at=ended_at,
                status="completed",
                input_summary="AWS Step Functions entered this workflow state.",
                output_summary="AWS Step Functions completed this workflow state.",
            )
        )
    for name, item in entered.items():
        normalized = name.lower().replace(" ", ".").replace("?", "")
        parent_name = STATE_PARENTS.get(name)
        parent_id = (
            f"aws.{parent_name.lower().replace(' ', '.').replace('?', '')}"
            if parent_name
            else None
        )
        kind = "tool" if "tool" in normalized else "agent"
        if "aggregate" in normalized:
            kind = "governance"
        elif "final" in normalized or "explain" in normalized:
            kind = "explainability"
        elif "prepare" in normalized or "planner" in normalized:
            kind = "orchestrator"
        started_at = item.get("timestamp", datetime.now(timezone.utc))
        events.append(
            ExecutionEvent(
                event_id=f"aws.{normalized}",
                parent_id=parent_id,
                request_id=request_id,
                kind=kind,
                agent=name,
                tool_name=name if kind == "tool" else None,
                started_at=started_at,
                ended_at=datetime.now(timezone.utc),
                status="running",
                input_summary="AWS Step Functions entered this workflow state.",
                output_summary="This AWS workflow state is currently running.",
            )
        )
    return events


def execution_status(
    request_id: str, *, step_functions_client: Any | None = None
) -> WorkflowStatusResponse:
    try:
        UUID(request_id)
    except ValueError as exc:
        raise ValueError("request_id must be a UUID") from exc
    state_machine_arn, _ = _configuration()
    execution_arn = _execution_arn(state_machine_arn, request_id)
    api = step_functions_client or client()
    try:
        description = api.describe_execution(executionArn=execution_arn)
        history = api.get_execution_history(
            executionArn=execution_arn,
            maxResults=1000,
            reverseOrder=False,
            includeExecutionData=False,
        )
    except Exception as exc:
        raise ExternalServiceError(
            f"AWS Step Functions could not read workflow status: {exc}"
        ) from exc
    status = description["status"]
    result = None
    error = description.get("error") or description.get("cause")
    if status == "SUCCEEDED":
        try:
            result = InvestmentAnalysisResponse.model_validate_json(description["output"])
        except (KeyError, ValueError) as exc:
            raise ExternalServiceError(
                "AWS Step Functions returned an invalid investment result"
            ) from exc
    return WorkflowStatusResponse(
        request_id=request_id,
        execution_arn=execution_arn,
        status=status,
        events=_history_events(request_id, history.get("events", [])),
        result=result,
        error=error,
    )
