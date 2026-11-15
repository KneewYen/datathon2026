from __future__ import annotations

from typing import Any, Dict

from app.agents.base import Agent
from app.domain.models import AgentFinding


class GrowthStrategyAgent(Agent):
    name = "growth_strategy_agent"
    role = "Assess growth exposure and concentration without forecasting returns."

    def plan(self, context: Dict[str, Any]) -> AgentFinding:
        if context.get("workflow") == "investment_purchase":
            return AgentFinding(
                agent=self.name,
                role=self.role,
                summary=(
                    f"Measure direct and ETF look-through {context['ticker']} exposure, then "
                    "simulate how the purchase changes growth concentration and account risk."
                ),
                requested_operations=["analyze_holdings_exposure", "simulate_account_purchase"],
            )
        return AgentFinding(
            agent=self.name,
            role=self.role,
            summary=(
                "Measure how reducing the growth sleeve changes historical volatility, "
                "drawdown, performance, and concentration."
            ),
            requested_operations=["risk_comparison", "performance_comparison"],
        )
