from __future__ import annotations

from typing import Any, Dict, Literal, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.agents.signals import sentiment as sentiment_agent
from app.domain.presets import PERSONAS
from app.services import sell_guard_service
from app.services.errors import ExternalServiceError, ServiceConfigurationError


router = APIRouter()


def _persona(persona_id: str) -> str:
    if persona_id not in PERSONAS:
        raise HTTPException(status_code=404, detail=f"unknown persona: {persona_id}")
    return persona_id


@router.get("/market")
def market() -> Dict[str, Any]:
    return sell_guard_service.market_status()


@router.post("/market/refresh")
def refresh_market() -> Dict[str, Any]:
    """Load the second dataset (the simulated market change) as the live market."""
    return sell_guard_service.refresh_market()


@router.post("/market/reset")
def reset_market() -> Dict[str, Any]:
    return sell_guard_service.reset_market()


@router.get("/portfolio/{persona_id}")
def portfolio(persona_id: str, account_type: Optional[str] = None) -> Dict[str, Any]:
    """Holdings for a persona on the current live market."""
    return sell_guard_service.portfolio(_persona(persona_id), account_type)


@router.get("/trade-check/{ticker}")
def trade_check(ticker: str, action: Literal["buy", "sell"]) -> Dict[str, Any]:
    """What the live market data and news say about buying or selling ``ticker``."""
    try:
        return sell_guard_service.evaluate(action, ticker)
    except LookupError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/sentiment/{ticker}")
def ticker_sentiment(ticker: str, half_life_days: float | None = None) -> Dict[str, Any]:
    """Deterministic sentiment evidence for one ticker (no model call)."""
    try:
        return sell_guard_service.sentiment_summary(ticker.upper(), half_life_days)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


class SentimentQuestion(BaseModel):
    question: str = Field(min_length=3, max_length=500)
    language: Literal["en", "fr"] = "en"


@router.post("/sentiment/ask")
def ask_sentiment(body: SentimentQuestion) -> Dict[str, Any]:
    """Bedrock decides which tickers to look up; the evidence still comes from deterministic code."""
    try:
        return sentiment_agent.ask(body.question, body.language)
    except ServiceConfigurationError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except ExternalServiceError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
