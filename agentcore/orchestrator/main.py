"""Orchestrator agent (AgentCore runtime): runs the four specialist agents in order.

For "should I buy or sell X?" it calls the Intake, Market, Classifier and Explainer agents, each its
own AgentCore runtime, and passes the evidence along. It does no calculation. Its model decides when
to call each tool, but the order is enforced here: a step whose inputs are missing runs the earlier
steps first, and any step the model skipped still runs, so every invocation is complete.

Runtime ARNs come from the environment: INTAKE_AGENT_ARN, MARKET_AGENT_ARN, CLASSIFIER_AGENT_ARN
and EXPLAINER_AGENT_ARN.
"""

from __future__ import annotations

import os
import sys
from typing import Any, Callable, Dict

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from bedrock_agentcore.runtime import BedrockAgentCoreApp  # noqa: E402

from common import AgentFailure, envelope, invoke_runtime  # noqa: E402

app = BedrockAgentCoreApp()

SYSTEM = """You are the Orchestrator of PortfolioGuard AI. For a buy or sell check, call these tools in this order,
each exactly once: intake_agent, market_agent, classifier_agent, explainer_agent. Never skip one and never call
them in another order. Do not write, change or summarise any result; reply with the single word done."""

ARN_ENV = {
    "Intake": "INTAKE_AGENT_ARN",
    "Market": "MARKET_AGENT_ARN",
    "Classifier": "CLASSIFIER_AGENT_ARN",
    "Explainer": "EXPLAINER_AGENT_ARN",
}


def _call(agent: str, payload: Dict[str, Any], session: str, invoker: Callable[..., Any]) -> Any:
    return invoker(os.getenv(ARN_ENV[agent], ""), {"payload": payload}, session)


class Run:
    """One trade check: the shared state the four tools read and write."""

    def __init__(self, p: Dict[str, Any], invoker: Callable[..., Any] = invoke_runtime):
        self.p = p
        self.invoker = invoker
        self.session = str(p.get("user_id") or "demo")
        self.done: Dict[str, Any] = {}
        self.trace: list = []

    def _step(self, agent: str, payload: Dict[str, Any], note: Callable[[Any], str]) -> Any:
        result = _call(agent, payload, self.session, self.invoker)
        self.done[agent] = result
        self.trace.append({"agent": agent, "action": note(result), "runtime": os.getenv(ARN_ENV[agent], "").rsplit("/", 1)[-1] or agent.lower()})
        return result

    def intake(self) -> Dict[str, Any]:
        if "Intake" in self.done:
            return self.done["Intake"]
        p = self.p
        return self._step(
            "Intake",
            {k: p.get(k) for k in ("persona", "account_type", "user_id", "message", "lang")},
            lambda who: (f"read {who.get('persona_name') or 'the described investor'} as a {who['risk_band']}-risk persona" if who.get("risk_band") else "no investor selected, so the check is not personalised")
            + (f"; {who['account_rule']}" if who.get("account_rule") else "")
            + (f"; {who['note']}" if who.get("note") else ""),
        )

    def market(self) -> Dict[str, Any]:
        if "Market" in self.done:
            return self.done["Market"]
        self.intake()
        return self._step(
            "Market",
            {"ticker": self.p["ticker"], "live": bool(self.p.get("live"))},
            lambda m: f"compare the market before and after the refresh: {m['tickers_falling_together']} of {m['tracked_tickers']} tracked tickers fell together",
        )

    def classify(self) -> Dict[str, Any]:
        if "Classifier" in self.done:
            return self.done["Classifier"]
        who, market = self.intake(), self.market()
        return self._step(
            "Classifier",
            {"action": self.p["action"], "ticker": self.p["ticker"], "market": market, "risk_band": who.get("risk_band")},
            lambda c: f"label the move {c['trade_check']['driver']}-driven and score it, citing {len(c['trade_check']['evidence'])} evidence items",
        )

    def explain(self) -> Dict[str, Any]:
        if "Explainer" in self.done:
            return self.done["Explainer"]
        who, classified = self.intake(), self.classify()
        p = self.p
        return self._step(
            "Explainer",
            {"action": p["action"], "ticker": p["ticker"], "result": classified["trade_check"], "intake": who,
             "persona": p.get("persona"), "account_type": p.get("account_type"), "live": bool(p.get("live")), "lang": p.get("lang", "en")},
            lambda e: e.get("note", "wrote the pop-up warning and the chat detail"),
        )

    def finish(self) -> Dict[str, Any]:
        """Run any step the model skipped, in order, and assemble the result the app expects."""
        explained = self.explain()
        classified = self.done["Classifier"]
        result = {**classified["trade_check"], "explanation": explained["explanation"]}
        if explained.get("persona_fit"):
            result["persona_fit"] = explained["persona_fit"]
        return {**result, "trace": self.trace, "intake": self.done["Intake"]}


def work(p: Dict[str, Any], invoker: Callable[..., Any] = invoke_runtime, use_model: bool = True) -> Dict[str, Any]:
    for field in ("action", "ticker"):
        if not p.get(field):
            raise AgentFailure(422, f"{field} is required")
    run = Run(p, invoker)
    if use_model:
        from strands import Agent, tool

        from common import model

        def intake_agent() -> dict:
            """Intake agent: who is asking, as a low, mid or high risk persona."""
            return run.intake()

        def market_agent() -> dict:
            """Market agent: what changed between the two market snapshots."""
            return run.market()

        def classifier_agent() -> dict:
            """Classifier agent: market-driven or company-driven, with scores and a sentiment label."""
            return run.classify()

        def explainer_agent() -> dict:
            """Explainer agent: the pop-up warning and the full chat detail."""
            return run.explain()

        try:
            Agent(
                name="orchestrator", model=model(), system_prompt=SYSTEM,
                tools=[tool(fn) for fn in (intake_agent, market_agent, classifier_agent, explainer_agent)],
                callback_handler=None,
            )(f"Check this {p['action']} of {p['ticker']}.")
        except AgentFailure:
            raise
        except Exception:  # the model path failed: the fixed order below still completes the check
            pass
    return run.finish()


@app.entrypoint
def invoke(payload, context=None):
    request = payload or {}
    return envelope(lambda: work(request.get("payload") or request))


if __name__ == "__main__":
    app.run()
