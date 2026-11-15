from __future__ import annotations

import os
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.agents.orchestrator import GlobalOrchestrator
from app.domain.models import AnalysisRequest, AnalysisResponse, ChallengeRequest, ChallengeResponse
from app.domain.presets import (
    CHALLENGE_PROMPTS,
    PERSONA_SCENARIOS,
    PERSONAS,
    STRATEGY_HOLDINGS,
    STRATEGY_LABELS,
)
from app.services.errors import ExternalServiceError, ServiceConfigurationError


router = APIRouter()
orchestrator = GlobalOrchestrator()


class ChatRequest(BaseModel):
    persona_id: Optional[str] = None
    user_id: str = "demo"
    message: str


class ApproveRequest(BaseModel):
    risk: Optional[str] = None


def _guard(call):
    try:
        return call()
    except ServiceConfigurationError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except ExternalServiceError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


def _run(request: AnalysisRequest) -> AnalysisResponse:
    return _guard(lambda: orchestrator.run(request))


def _challenge(request: ChallengeRequest) -> ChallengeResponse:
    try:
        return _guard(lambda: orchestrator.challenge(request.persona_id, request.message))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/analysis", response_model=AnalysisResponse)
def analysis(request: AnalysisRequest) -> AnalysisResponse:
    return _run(request)


@router.post("/analysis/persona/{persona_id}", response_model=AnalysisResponse)
def persona_analysis(persona_id: str) -> AnalysisResponse:
    """Run the scenario designed for this persona's test in the case brief."""
    try:
        request = AnalysisRequest.for_persona(persona_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return _run(request)


@router.post("/challenge", response_model=ChallengeResponse)
def challenge(request: ChallengeRequest) -> ChallengeResponse:
    return _challenge(request)


@router.post("/chat")
def chat(request: ChatRequest) -> Any:
    """Route persona requests to the challenge or scenario analysis; otherwise the conversational flow."""
    if request.persona_id:
        if request.persona_id not in PERSONA_SCENARIOS:
            raise HTTPException(status_code=422, detail=f"unknown persona: {request.persona_id}")
        if orchestrator.is_challenge(request.persona_id, request.message):
            return _challenge(ChallengeRequest(persona_id=request.persona_id, message=request.message))
        return _run(AnalysisRequest.for_persona(request.persona_id))
    return orchestrator.chat(request.user_id, request.message)


@router.post("/actions/{action_id}/approve")
def approve(action_id: str, request: ApproveRequest) -> Dict[str, Any]:
    return orchestrator.approve(action_id, request.risk)


@router.post("/actions/{action_id}/reject")
def reject(action_id: str) -> Dict[str, Any]:
    return orchestrator.reject(action_id)


@router.get("/accounts")
def accounts(user_id: str = "demo") -> List[Dict[str, Any]]:
    from app import store

    return store.accounts(user_id)


@router.get("/meta")
def meta() -> Dict[str, Any]:
    from app.agents import knowledge
    from app.profiles import PROFILES

    region = os.getenv("AWS_REGION")
    function_name = os.getenv("LAMBDA_FUNCTION_NAME")
    model_id = os.getenv("BEDROCK_MODEL_ID")
    data_bucket = os.getenv("S3_BUCKET")
    data_prefix = os.getenv("DATA_PREFIX", "starter/v1")

    return {
        "profiles": PROFILES,
        "faq": knowledge.suggestions(),
        "scenarios": PERSONA_SCENARIOS,
        "challenge_prompts": CHALLENGE_PROMPTS,
        "personas": {
            persona_id: {
                "name": persona["name"],
                "account_type": persona["account_type"],
                "portfolio_value": persona["portfolio_value"],
                "risk_budget": persona["risk_budget"],
                "esg_excluded_sectors": persona["esg_excluded_sectors"],
            }
            for persona_id, persona in PERSONAS.items()
        },
        "strategy_holdings": STRATEGY_HOLDINGS,
        "strategy_labels": STRATEGY_LABELS,
        "integrations": {
            "region": region,
            "lambda": {
                "configured": bool(region and function_name),
                "label": "AWS Lambda financial tools",
                "detail": function_name or "LAMBDA_FUNCTION_NAME is not configured",
            },
            "bedrock": {
                "configured": bool(region and model_id),
                "label": "Amazon Bedrock explanation",
                "detail": model_id or "BEDROCK_MODEL_ID is not configured",
            },
            "dataset": {
                "configured": bool(region and function_name and data_prefix),
                "label": "Versioned Amazon S3 dataset",
                "detail": (
                    f"s3://{data_bucket}/{data_prefix}/"
                    if data_bucket
                    else f"{data_prefix}/ via Lambda; verified after a successful live run"
                ),
            },
        },
    }
