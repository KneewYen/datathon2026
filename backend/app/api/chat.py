from typing import Any, Dict, List, Optional

from fastapi import APIRouter
from pydantic import BaseModel

from app.agents.orchestrator import GlobalOrchestrator

router = APIRouter()
orchestrator = GlobalOrchestrator()


class ChatRequest(BaseModel):
    persona_id: str  # amira | mateo | robert
    message: str


class ChatResponse(BaseModel):
    answer: str
    metrics: Dict[str, Any] = {}
    trace: List[Dict[str, Any]] = []
    warnings: List[str] = []


@router.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest) -> ChatResponse:
    return ChatResponse(**orchestrator.run(req.persona_id, req.message))
