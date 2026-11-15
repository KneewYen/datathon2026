from __future__ import annotations

from typing import Any, Dict

from app.agents.base import Agent
from app.domain.models import AgentFinding


class BalancedIndexStrategyAgent(Agent):
    name = "balanced_index_strategy_agent"
    role = "Assess the broad index sleeve (XIU.TO, SPY, XBB.TO, AGG) as a diversifier."

    def plan(self, context: Dict[str, Any]) -> AgentFinding:
        return AgentFinding(
            agent=self.name,
            role=self.role,
            summary=(
                "Measure how broad index exposure changes concentration, volatility, and 2022 stress losses."
            ),
            requested_operations=["risk_comparison", "stress_replay"],
        )