from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.agents.orchestrator import GlobalOrchestrator
from app.domain.models import AnalysisRequest, AnalysisResponse
from app.services.errors import ExternalServiceError, ServiceConfigurationError


router = APIRouter()
orchestrator = GlobalOrchestrator()


class ChatRequest(BaseModel):
    persona_id: str
    message: str


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


@router.post("/chat", response_model=AnalysisResponse)
def chat(request: ChatRequest) -> AnalysisResponse:
    """Compatibility route that runs the focused TFSA demo scenario."""
    try:
        analysis_request = AnalysisRequest(
            persona_id=request.persona_id,
            question=request.message,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return _run(analysis_request)
