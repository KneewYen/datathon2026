from __future__ import annotations

from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.agents.orchestrator import GlobalOrchestrator
from app.domain.models import AnalysisRequest, AnalysisResponse
from app.services.errors import ExternalServiceError, ServiceConfigurationError


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

    return {"profiles": PROFILES, "faq": knowledge.suggestions()}
