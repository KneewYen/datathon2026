from __future__ import annotations

import os
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.agents.orchestrator import GlobalOrchestrator
from app.domain.models import AnalysisRequest, AnalysisResponse
from app.i18n import normalize
from app.services.errors import ExternalServiceError, ServiceConfigurationError


router = APIRouter()
orchestrator = GlobalOrchestrator()


class ChatRequest(BaseModel):
    persona_id: Optional[str] = None
    user_id: str = "demo"
    message: str
    lang: str = "en"


class ApproveRequest(BaseModel):
    risk: Optional[str] = None
    lang: str = "en"


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


@router.post("/chat")
def chat(request: ChatRequest) -> Any:
    """Run the focused analysis or the conversational account flow."""
    if request.persona_id:
        try:
            return _run(
                AnalysisRequest(
                    persona_id=request.persona_id, question=request.message, language=normalize(request.lang)
                )
            )
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
    return orchestrator.chat(request.user_id, request.message, request.lang)


@router.post("/actions/{action_id}/approve")
def approve(action_id: str, request: ApproveRequest) -> Dict[str, Any]:
    return orchestrator.approve(action_id, request.risk, request.lang)


@router.post("/actions/{action_id}/reject")
def reject(action_id: str, lang: str = "en") -> Dict[str, Any]:
    return orchestrator.reject(action_id, lang)


@router.get("/accounts")
def accounts(user_id: str = "demo") -> List[Dict[str, Any]]:
    from app import store

    return store.accounts(user_id)


@router.delete("/accounts/{account_id}")
def delete_account(account_id: str, user_id: str = "demo") -> Dict[str, bool]:
    from app import store

    if not store.delete_account(user_id, account_id):
        raise HTTPException(status_code=404, detail=f"Account {account_id} not found")
    return {"deleted": True}



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
        },
    }
