from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime, timezone

from app.domain.models import ResearchResult


class ResearchProvider(ABC):
    @abstractmethod
    def search_company(self, ticker: str) -> ResearchResult:
        raise NotImplementedError


class UnavailableResearchProvider(ResearchProvider):
    """Fail transparently until an approved live news/OSINT provider is configured."""

    def search_company(self, ticker: str) -> ResearchResult:
        return ResearchResult(
            status="unavailable",
            provider="not-configured",
            retrieved_at=datetime.now(timezone.utc),
            items=[],
            limitations=[
                f"No approved live news provider is configured for {ticker}; no news claims were generated.",
                "The organizer dataset contains prices and macro observations, but no news feed.",
            ],
        )
