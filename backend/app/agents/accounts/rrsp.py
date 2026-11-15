from __future__ import annotations

from typing import Any, Dict

from app.agents.accounts.base import AccountAgent
from app.domain.models import AgentFinding


class RRSPAccountAgent(AccountAgent):
    name = "rrsp_account_agent"
    role = "Coordinate strategy analysis within a fictional RRSP scenario."
    account_type = "RRSP"
    investment_strategy_names = ("dividend", "preservation")

    def plan(self, context: Dict[str, Any]) -> AgentFinding:
        if context.get("workflow") == "investment_purchase":
            return AgentFinding(
                agent=self.name,
                role=self.role,
                summary=(
                    f"Evaluate {context['ticker']} against the RRSP's conservative retirement "
                    "objective, income allocation, cash floor, and concentration limit."
                ),
                requested_operations=["analyze_holdings_exposure", "simulate_account_purchase"],
            )
        return AgentFinding(
            agent=self.name,
            role=self.role,
            summary=(
                "Evaluate the requested RRSP strategy shift using explicit account "
                "assumptions without calculating personal tax outcomes."
            ),
            requested_operations=["compare_strategy_shift"],
        )
