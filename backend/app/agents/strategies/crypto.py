from __future__ import annotations

from typing import Any, Dict

from app.agents.base import Agent
from app.domain.models import AgentFinding


class CryptoStrategyAgent(Agent):
    name = "crypto_strategy_agent"
    role = "Assess the crypto sleeve (BTC-USD, ETH-USD) against the persona's crypto cap."

    def plan(self, context: Dict[str, Any]) -> AgentFinding:
        return AgentFinding(
            agent=self.name,
            role=self.role,
            summary=(
                "Measure the crypto sleeve's contribution to volatility and drawdown; crypto size is governed by a hard persona cap."
            ),
            requested_operations=["risk_comparison", "stress_replay"],
        )