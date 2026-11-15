from __future__ import annotations

import os
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.agents.orchestrator import GlobalOrchestrator
from app.domain.models import (
    AnalysisRequest,
    AnalysisResponse,
    InvestmentAnalysisRequest,
    InvestmentAnalysisResponse,
    WorkflowStartResponse,
    WorkflowStatusResponse,
)
from app.services.errors import ExternalServiceError, ServiceConfigurationError
from app.services.step_functions import execution_status, start_execution


router = APIRouter()
orchestrator = GlobalOrchestrator()


class ChatRequest(BaseModel):
    persona_id: Optional[str] = None
    user_id: str = "demo"
    message: str


class ApproveRequest(BaseModel):
    risk: Optional[str] = None


def _run(request: AnalysisRequest) -> AnalysisResponse:
    try:
        return orchestrator.run(request)
    except ServiceConfigurationError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except ExternalServiceError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.post("/analysis", response_model=AnalysisResponse)
def analysis(request: AnalysisRequest) -> AnalysisResponse:
    return _run(request)


@router.post(
    "/investment-analysis",
    response_model=InvestmentAnalysisResponse | WorkflowStartResponse,
    status_code=200,
)
def investment_analysis(
    request: InvestmentAnalysisRequest,
) -> InvestmentAnalysisResponse | WorkflowStartResponse:
    try:
        if os.getenv("ORCHESTRATION_MODE", "local") == "step-functions":
            return start_execution(request)
        return orchestrator.analyze_investment(request)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except ServiceConfigurationError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except ExternalServiceError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.get(
    "/investment-analysis/executions/{request_id}",
    response_model=WorkflowStatusResponse,
)
def investment_analysis_status(request_id: str) -> WorkflowStatusResponse:
    try:
        return execution_status(request_id)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except ServiceConfigurationError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except ExternalServiceError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.post("/chat")
def chat(request: ChatRequest) -> Any:
    """Run the focused analysis or the conversational account flow."""
    if request.persona_id:
        try:
            return _run(AnalysisRequest(persona_id=request.persona_id, question=request.message))
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
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
            "orchestration": {
                "configured": bool(
                    os.getenv("ORCHESTRATION_MODE") == "step-functions"
                    and os.getenv("INVESTMENT_STATE_MACHINE_ARN")
                ),
                "label": "AWS Step Functions investment workflow",
                "detail": (
                    os.getenv("INVESTMENT_STATE_MACHINE_ARN")
                    or "Local in-process orchestration"
                ),
            },
        },
    }
