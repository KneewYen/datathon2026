from __future__ import annotations

from typing import Any, Dict

from app.agents.base import Agent
from app.domain.models import AgentFinding


class CapitalPreservationStrategyAgent(Agent):
    name = "capital_preservation_strategy_agent"
    role = "Assess loss sensitivity and stabilizing assets for the stated horizon."

    def plan(self, context: Dict[str, Any]) -> AgentFinding:
        if context.get("workflow") == "investment_purchase":
            return AgentFinding(
                agent=self.name,
                role=self.role,
                summary=(
                    f"Simulate {context['ticker']} in the conservative account and enforce "
                    "cash, concentration, volatility, and drawdown constraints."
                ),
                requested_operations=["simulate_account_purchase"],
            )
        return AgentFinding(
            agent=self.name,
            role=self.role,
            summary="Retain the unchanged preservation sleeve and measure account-level drawdown.",
            requested_operations=["risk_comparison"],
        )
