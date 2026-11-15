"""Constrained Amazon Bedrock runtime for named PortfolioGuard agents."""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

import boto3

from app.domain.models import (
    EvidenceRecord,
    ExecutionEvent,
    Explanation,
    GovernanceFinding,
)
from app.services.bedrock import _extract_json, _validate_result
from app.services.errors import ExternalServiceError, ServiceConfigurationError


@dataclass(frozen=True)
class AgentDefinition:
    name: str
    responsibility: str
    allowed_agents: tuple[str, ...] = ()
    allowed_operations: tuple[str, ...] = ()


AGENTS = {
    "global_orchestrator": AgentDefinition(
        "global_orchestrator",
        "Identify relevant accounts and coordinate a cross-account investment analysis.",
        allowed_agents=("tfsa_account_agent", "rrsp_account_agent"),
    ),
    "tfsa_account_agent": AgentDefinition(
        "tfsa_account_agent",
        "Assess fit with the fictional aggressive, long-horizon TFSA objective.",
        allowed_agents=("growth_strategy_agent", "momentum_strategy_agent"),
    ),
    "rrsp_account_agent": AgentDefinition(
        "rrsp_account_agent",
        "Assess fit with the fictional conservative retirement RRSP objective.",
        allowed_agents=(
            "dividend_strategy_agent",
            "capital_preservation_strategy_agent",
        ),
    ),
    "growth_strategy_agent": AgentDefinition(
        "growth_strategy_agent",
        "Evaluate growth exposure, technology concentration, and holdings overlap.",
        allowed_operations=("analyze_holdings_exposure", "simulate_account_purchase"),
    ),
    "momentum_strategy_agent": AgentDefinition(
        "momentum_strategy_agent",
        "Evaluate historical market behavior and request approved research.",
        allowed_operations=("market_snapshot", "research_news"),
    ),
    "dividend_strategy_agent": AgentDefinition(
        "dividend_strategy_agent",
        "Evaluate income-oriented compatibility and allocation trade-offs.",
        allowed_operations=("analyze_holdings_exposure",),
    ),
    "capital_preservation_strategy_agent": AgentDefinition(
        "capital_preservation_strategy_agent",
        "Evaluate downside risk, cash floors, concentration, and objective conflicts.",
        allowed_operations=("simulate_account_purchase",),
    ),
}

ROUTING_STAGE_ROLES = {
    "account": {"tfsa_account_agent", "rrsp_account_agent"},
    "strategy": {
        "growth_strategy_agent",
        "momentum_strategy_agent",
        "dividend_strategy_agent",
        "capital_preservation_strategy_agent",
    },
}


SYSTEM_PROMPT = """You are one named component in PortfolioGuard AI.
Return JSON only. Never calculate, estimate, or repeat financial numbers. Never claim that a
trade will execute. Use only the supplied fictional account context and supported capability
names. Provide a concise qualitative summary and choose only from the explicitly allowed
agents and operations. The JSON shape is:
{"summary":"qualitative finding without digits","activated_agents":[],"requested_operations":[]}.
"""

NUMERIC_SUMMARY_FALLBACK = (
    "The model returned a permitted routing decision, but its numeric rationale was withheld "
    "by deterministic governance policy."
)
EMPTY_SUMMARY_FALLBACK = (
    "The model returned a permitted routing decision without a usable qualitative rationale."
)


def _client():
    region = os.getenv("AWS_REGION")
    if not region:
        raise ServiceConfigurationError("AWS_REGION is required for Amazon Bedrock")
    return boto3.client("bedrock-runtime", region_name=region)


def _response_document(response: dict) -> dict:
    try:
        text = response["output"]["message"]["content"][0]["text"]
        value = _extract_json(text)
    except (KeyError, IndexError, TypeError, ExternalServiceError) as exc:
        raise ExternalServiceError("Bedrock agent returned invalid JSON") from exc
    if not isinstance(value, dict):
        raise ExternalServiceError("Bedrock agent output must be an object")
    return value


def invoke_named_agent(
    role: str,
    context: dict,
    *,
    request_id: str,
    parent_id: str,
    bedrock_client: Any | None = None,
) -> dict:
    definition = AGENTS.get(role)
    if definition is None:
        raise ValueError(f"unsupported agent role: {role}")
    model_id = os.getenv("BEDROCK_MODEL_ID")
    if not model_id:
        raise ServiceConfigurationError("BEDROCK_MODEL_ID is required")
    started_at = datetime.now(timezone.utc)
    packet = {
        "agent": definition.name,
        "responsibility": definition.responsibility,
        "allowed_agents": definition.allowed_agents,
        "allowed_operations": definition.allowed_operations,
        "context": context,
    }
    try:
        response = (bedrock_client or _client()).converse(
            modelId=model_id,
            system=[{"text": SYSTEM_PROMPT}],
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "text": "Review this validated workflow context:\n"
                            + json.dumps(packet, separators=(",", ":"))
                        }
                    ],
                }
            ],
            inferenceConfig={"maxTokens": 350, "temperature": 0.0},
        )
        document = _response_document(response)
    except (ServiceConfigurationError, ExternalServiceError):
        raise
    except Exception as exc:
        raise ExternalServiceError(f"Bedrock agent {role} failed: {exc}") from exc
    summary = document.get("summary")
    activated_agents = document.get("activated_agents", [])
    requested_operations = document.get("requested_operations", [])
    if not isinstance(activated_agents, list) or any(
        not isinstance(item, str) for item in activated_agents
    ):
        raise ExternalServiceError(f"Bedrock agent {role} selected an unsupported agent")
    unsupported_agents = set(activated_agents) - set(definition.allowed_agents)
    if unsupported_agents and definition.allowed_agents:
        raise ExternalServiceError(f"Bedrock agent {role} selected an unsupported agent")
    if unsupported_agents:
        activated_agents = []
        agent_selection_policy = "unauthorized_leaf_delegation_ignored"
    else:
        agent_selection_policy = "model_selection_accepted"
    if not isinstance(requested_operations, list) or not set(
        requested_operations
    ).issubset(definition.allowed_operations):
        raise ExternalServiceError(f"Bedrock agent {role} selected an unsupported operation")
    if not isinstance(summary, str) or not summary.strip():
        safe_summary = EMPTY_SUMMARY_FALLBACK
        summary_policy = "empty_rationale_replaced"
    elif re.search(r"\d", summary):
        safe_summary = NUMERIC_SUMMARY_FALLBACK
        summary_policy = "numeric_rationale_withheld"
    else:
        safe_summary = summary.strip()
        summary_policy = "model_rationale_accepted"
    finding = {
        "agent": definition.name,
        "role": definition.responsibility,
        "summary": safe_summary,
        "summary_policy": summary_policy,
        "agent_selection_policy": agent_selection_policy,
        "requested_operations": requested_operations,
        "evidence_ids": [],
    }
    event = ExecutionEvent(
        event_id=f"agent.{definition.name}",
        parent_id=parent_id,
        request_id=request_id,
        kind="orchestrator" if role == "global_orchestrator" else "agent",
        agent=definition.name,
        started_at=started_at,
        ended_at=datetime.now(timezone.utc),
        status="completed",
        input_summary=definition.responsibility,
        output_summary=safe_summary,
    )
    return {
        "role": role,
        "finding": finding,
        "activated_agents": activated_agents,
        "requested_operations": requested_operations,
        "summary_policy": summary_policy,
        "agent_selection_policy": agent_selection_policy,
        "model_id": model_id,
        "event": event.model_dump(mode="json"),
    }


def invoke_routed_agent(
    role: str,
    context: dict,
    *,
    routing_stage: str,
    expected_role: str,
    request_id: str,
    parent_id: str,
    parent_account_role: str | None = None,
    bedrock_client: Any | None = None,
) -> dict:
    """Invoke only a role already selected by a validated workflow route."""
    allowed = ROUTING_STAGE_ROLES.get(routing_stage)
    if allowed is None or role != expected_role or role not in allowed:
        raise ValueError("agent route does not match the authorized routing stage")
    if routing_stage == "strategy":
        parent = AGENTS.get(parent_account_role or "")
        if parent is None or role not in parent.allowed_agents:
            raise ValueError("specialized agent is not permitted by its account orchestrator")
    return invoke_named_agent(
        role,
        context,
        request_id=request_id,
        parent_id=parent_id,
        bedrock_client=bedrock_client,
    )


def invoke_explainability_agent(
    aggregation: dict,
    *,
    bedrock_client: Any | None = None,
) -> dict:
    model_id = os.getenv("BEDROCK_MODEL_ID")
    if not model_id:
        raise ServiceConfigurationError("BEDROCK_MODEL_ID is required")
    evidence = [EvidenceRecord.model_validate(item) for item in aggregation["evidence"]]
    governance = [
        GovernanceFinding.model_validate(item) for item in aggregation["governance"]
    ]
    packet = {
        "question": aggregation["question"],
        "workflow": "aws_step_functions_cross_account_investment",
        "verified_evidence": [item.model_dump() for item in evidence],
        "account_options": aggregation["account_options"],
        "governance": [item.model_dump() for item in governance],
        "limitations": aggregation["limitations"],
        "allowed_evidence_ids": [item.evidence_id for item in evidence],
        "instruction": (
            "Compare account suitability without introducing numbers or implying trade execution."
        ),
    }
    started_at = datetime.now(timezone.utc)
    try:
        response = (bedrock_client or _client()).converse(
            modelId=model_id,
            system=[
                {
                    "text": (
                        "Use only the supplied evidence. Return JSON with answer, evidence_ids, "
                        "and limitations. Do not include numeric characters in the answer."
                    )
                }
            ],
            messages=[
                {
                    "role": "user",
                    "content": [{"text": json.dumps(packet, separators=(",", ":"))}],
                }
            ],
            inferenceConfig={"maxTokens": 500, "temperature": 0.0},
        )
        validated = _validate_result(_response_document(response), packet, model_id)
    except (ServiceConfigurationError, ExternalServiceError):
        raise
    except Exception as exc:
        raise ExternalServiceError(f"Bedrock explainability agent failed: {exc}") from exc
    explanation = Explanation.model_validate(validated)
    event = ExecutionEvent(
        event_id="agent.explainability_agent",
        parent_id="governance.review",
        request_id=aggregation["request_id"],
        kind="explainability",
        agent="explainability_agent",
        started_at=started_at,
        ended_at=datetime.now(timezone.utc),
        status="completed",
        evidence_ids=explanation.evidence_ids,
        input_summary="Synthesize only validated evidence and governance findings.",
        output_summary="Produced a grounded cross-account explanation through Amazon Bedrock.",
    )
    return {
        "explanation": explanation.model_dump(mode="json"),
        "event": event.model_dump(mode="json"),
    }
