from __future__ import annotations

from typing import Any, Dict

from app.agents.base import Agent
from app.domain.models import AgentFinding


class ESGStrategyAgent(Agent):
    name = "esg_strategy_agent"
    role = "Assess the ESG-screened sleeve (ESGV, FTS.TO, CNR.TO) against the investor's values and risk."

    def plan(self, context: Dict[str, Any]) -> AgentFinding:
        return AgentFinding(
            agent=self.name,
            role=self.role,
            summary=(
                "Measure how the ESG sleeve changes risk, and confirm it holds no excluded-sector assets; sector screening cannot verify company controversies."
            ),
            requested_operations=["risk_comparison", "stress_replay"],
        )