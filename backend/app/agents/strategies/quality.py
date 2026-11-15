from __future__ import annotations

from typing import Any, Dict

from app.agents.base import Agent
from app.domain.models import AgentFinding


class QualityStrategyAgent(Agent):
    name = "quality_strategy_agent"
    role = "Assess the established-company quality sleeve (CNR.TO, CSU.TO, MSFT, JNJ, PG)."

    def plan(self, context: Dict[str, Any]) -> AgentFinding:
        return AgentFinding(
            agent=self.name,
            role=self.role,
            summary=(
                "Measure the quality sleeve's effect on drawdown and 2022 stress behaviour without assuming quality guarantees stability."
            ),
            requested_operations=["risk_comparison", "stress_replay"],
        )