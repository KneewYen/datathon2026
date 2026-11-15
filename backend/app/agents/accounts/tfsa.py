from __future__ import annotations

from typing import Any, Dict

from app.agents.accounts.base import AccountAgent
from app.domain.models import AgentFinding


class TFSAAccountAgent(AccountAgent):
    name = "tfsa_account_agent"
    role = "Coordinate strategy analysis within the fictional TFSA scenario."
    account_type = "TFSA"
    investment_strategy_names = ("growth", "momentum")

    def plan(self, context: Dict[str, Any]) -> AgentFinding:
        if context.get("workflow") == "investment_purchase":
            return AgentFinding(
                agent=self.name,
                role=self.role,
                summary=(
                    f"Evaluate {context['ticker']} against the TFSA's aggressive, long-horizon "
                    "growth objective and its explicit concentration and cash constraints."
                ),
                requested_operations=["analyze_holdings_exposure", "simulate_account_purchase"],
            )
        return AgentFinding(
            agent=self.name,
            role=self.role,
            summary=(
                "Evaluate the requested TFSA strategy shift at the account level, "
                "then compare the current and proposed portfolio with deterministic tools."
            ),
            requested_operations=["compare_strategy_shift"],
        )
