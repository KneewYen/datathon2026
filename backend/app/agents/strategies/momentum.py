from __future__ import annotations

from typing import Any, Dict

from app.agents.base import Agent
from app.domain.models import AgentFinding


class MomentumStrategyAgent(Agent):
    name = "momentum_strategy_agent"
    role = "Describe transparent trailing-price signals without predicting returns."

    def plan(self, context: Dict[str, Any]) -> AgentFinding:
        if context.get("workflow") == "investment_purchase":
            return AgentFinding(
                agent=self.name,
                role=self.role,
                summary=(
                    f"Describe {context['ticker']}'s historical momentum and downside behavior, "
                    "and request recent research without forecasting its return."
                ),
                requested_operations=["market_snapshot", "research_news"],
            )
        return AgentFinding(
            agent=self.name,
            role=self.role,
            summary="Retain the unchanged momentum sleeve and disclose its descriptive role.",
            requested_operations=["portfolio_snapshot"],
        )
