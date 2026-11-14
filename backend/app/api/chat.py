from typing import Any, Dict, List, Optional

from fastapi import APIRouter
from pydantic import BaseModel

from app import store
from app.agents import knowledge
from app.agents.orchestrator import GlobalOrchestrator
from app.profiles import PROFILES

router = APIRouter()
orchestrator = GlobalOrchestrator()


class ChatRequest(BaseModel):
    user_id: str = "demo"
    message: str


class ApproveRequest(BaseModel):
    risk: Optional[str] = None


class ChatResponse(BaseModel):
    answer: str
    trace: List[Dict[str, Any]] = []
    metrics: Dict[str, Any] = {}
    sources: List[str] = []
    warnings: List[str] = []
    proposal: Optional[Dict[str, Any]] = None
    suggestions: List[str] = []


@router.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest):
    return orchestrator.chat(req.user_id, req.message)


@router.post("/actions/{action_id}/approve", response_model=ChatResponse)
def approve(action_id: str, req: ApproveRequest):
    return orchestrator.approve(action_id, req.risk)


@router.post("/actions/{action_id}/reject", response_model=ChatResponse)
def reject(action_id: str):
    return orchestrator.reject(action_id)


@router.get("/accounts")
def accounts(user_id: str = "demo"):
    return store.accounts(user_id)


@router.get("/meta")
def meta():
    return {"profiles": PROFILES, "faq": knowledge.suggestions()}
