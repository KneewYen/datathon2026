from __future__ import annotations

from typing import Dict, Iterable, Type

from app.agents.base import Agent
from app.agents.strategies.dividend import DividendStrategyAgent
from app.agents.strategies.growth import GrowthStrategyAgent
from app.agents.strategies.momentum import MomentumStrategyAgent
from app.agents.strategies.preservation import CapitalPreservationStrategyAgent
from app.domain.models import AgentFinding, AnalysisRequest


STRATEGY_AGENTS: Dict[str, Type[Agent]] = {
    "growth": GrowthStrategyAgent,
    "dividend": DividendStrategyAgent,
    "momentum": MomentumStrategyAgent,
    "preservation": CapitalPreservationStrategyAgent,
}


class AccountAgent(Agent):
    account_type = ""
    investment_strategy_names: tuple[str, ...] = ()

    def relevant_strategies(self, request: AnalysisRequest) -> Iterable[str]:
        return dict.fromkeys(
            [request.shift.from_strategy, request.shift.to_strategy]
        ).keys()

    def delegate(self, request: AnalysisRequest) -> list[AgentFinding]:
        context = {
            "persona_id": request.persona_id,
            "account_type": request.account_type,
            "question": request.question,
            "shift": request.shift.model_dump(),
        }
        return [STRATEGY_AGENTS[name]().plan(context) for name in self.relevant_strategies(request)]

    def delegate_investment(
        self, account: dict, question: str, ticker: str
    ) -> list[AgentFinding]:
        context = {
            "workflow": "investment_purchase",
            "account": account,
            "account_type": account["type"],
            "question": question,
            "ticker": ticker,
        }
        return [
            STRATEGY_AGENTS[name]().plan(context)
            for name in self.investment_strategy_names
            if account["strategy_allocations"].get(name, 0) > 0
        ]
