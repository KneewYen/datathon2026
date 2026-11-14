from __future__ import annotations

import re
from typing import Any, Callable, Dict, List
from uuid import uuid4

from app.agents.accounts import RRSPAccountAgent, TFSAAccountAgent
from app.agents.explainability import ExplainabilityAgent
from app.agents.governance import GovernanceAgent
from app.agents.profile import get_persona
from app.agents import account_creation, knowledge, profile
from app import store
from app.profiles import PROFILES
from app.agents.signals import macro
from app.domain.models import (
    AnalysisRequest,
    AnalysisResponse,
    MetricEvidence,
    PerformancePoint,
    TraceStep,
)
from app.domain.presets import STRATEGY_HOLDINGS
from app.services.lambda_tools import invoke

DISCLAIMER = "Simulation only. Not financial advice."


ACCOUNT_AGENTS = {
    "TFSA": TFSAAccountAgent,
    "RRSP": RRSPAccountAgent,
}


class GlobalOrchestrator:
    """Coordinate observable agent delegation and real AWS tool calls."""

    def __init__(
        self,
        financial_tool: Callable[[str, Dict], Dict] = invoke,
        explainability_agent: ExplainabilityAgent | None = None,
    ):
        self.financial_tool = financial_tool
        self.explainability_agent = explainability_agent or ExplainabilityAgent()
        self.governance_agent = GovernanceAgent()

    def run(self, request: AnalysisRequest) -> AnalysisResponse:
        analysis_id = str(uuid4())
        persona = get_persona(request.persona_id)
        account_agent = ACCOUNT_AGENTS[request.account_type]()
        account_finding = account_agent.plan(request.model_dump(mode="json"))
        strategy_findings = account_agent.delegate(request)
        delegated_names = [finding.agent for finding in strategy_findings]

        trace = [
            TraceStep(
                step_id="orchestrator.plan",
                agent="global_orchestrator",
                action="Resolve persona, account, and requested scenario",
                delegated_to=[account_agent.name],
                details={
                    "persona": persona["name"],
                    "account_type": request.account_type,
                },
            ),
            TraceStep(
                step_id="account.delegate",
                parent_id="orchestrator.plan",
                agent=account_agent.name,
                action="Delegate the account scenario to relevant strategy agents",
                delegated_to=delegated_names,
            ),
        ]
        for index, finding in enumerate(strategy_findings, start=1):
            trace.append(
                TraceStep(
                    step_id=f"strategy.{index}",
                    parent_id="account.delegate",
                    agent=finding.agent,
                    action=finding.summary,
                    details={"requested_operations": finding.requested_operations},
                )
            )

        lambda_payload = request.model_dump(mode="json")
        lambda_payload.update(
            {
                "analysis_id": analysis_id,
                "strategy_holdings": STRATEGY_HOLDINGS,
            }
        )
        calculation = self.financial_tool("compare_strategy_shift", lambda_payload)
        metrics = [MetricEvidence.model_validate(item) for item in calculation["metrics"]]
        evidence_ids = [metric.evidence_id for metric in metrics]
        trace.append(
            TraceStep(
                step_id="tool.financial_lambda",
                parent_id="account.delegate",
                agent="aws_financial_tools",
                action="Calculate current and proposed portfolio metrics in AWS Lambda",
                evidence_ids=evidence_ids,
                details={"aws_request_id": calculation.get("aws_request_id", "unknown")},
            )
        )

        governance = self.governance_agent.evaluate(
            request, calculation["conclusion"], metrics
        )
        trace.append(
            TraceStep(
                step_id="governance.review",
                parent_id="orchestrator.plan",
                agent=self.governance_agent.name,
                action="Apply simulation, profile, evidence, and trade-off controls",
                evidence_ids=sorted(
                    {
                        evidence_id
                        for finding in governance
                        for evidence_id in finding.evidence_ids
                    }
                ),
            )
        )

        explanation = self.explainability_agent.explain(
            request.question,
            calculation["conclusion"],
            metrics,
            governance,
            calculation["assumptions"],
            calculation["limitations"],
        )
        trace.append(
            TraceStep(
                step_id="explainability.synthesize",
                parent_id="governance.review",
                agent=self.explainability_agent.name,
                action="Use Amazon Bedrock to synthesize a grounded explanation",
                evidence_ids=explanation.evidence_ids,
                details={"model_id": explanation.model_id},
            )
        )

        return AnalysisResponse(
            analysis_id=analysis_id,
            question=request.question,
            persona_id=request.persona_id,
            account_type=request.account_type,
            answer=explanation.answer,
            conclusion=calculation["conclusion"],
            current_allocations=calculation["current_allocations"],
            proposed_allocations=calculation["proposed_allocations"],
            metrics=metrics,
            performance_series=[
                PerformancePoint.model_validate(item)
                for item in calculation["performance_series"]
            ],
            agent_findings=[account_finding, *strategy_findings],
            governance=governance,
            trace=trace,
            assumptions=calculation["assumptions"],
            limitations=[*calculation["limitations"], *explanation.limitations],
            data_sources=calculation["data_sources"],
            model_id=explanation.model_id,
        )

    def chat(self, user_id: str, message: str) -> Dict[str, Any]:
        """Handle the conversational account and knowledge-base flow."""
        trace: List[Dict[str, Any]] = [{"agent": "Global Orchestrator", "action": "detect intent"}]
        if self._is_create_intent(message):
            trace.append({"agent": "Investor Profile Agent", "action": "read horizon and risk, recommend account"})
            recommendation = profile.recommend(message)
            if recommendation.get("needs") == "horizon":
                return self._reply(
                    "What's the time horizon for this account?",
                    trace,
                    suggestions=["Create a short-term account", "Create a mid-term account", "Create a long-term account"],
                )
            trace.append({"agent": "Governance Agent", "action": "check fit with profile, require user approval"})
            action_id = store.new_id()
            store.PENDING[action_id] = {"user_id": user_id, "type": "create_account", "payload": recommendation}
            return self._reply(
                f"I recommend a **{recommendation['account_type']}** account for "
                f"{recommendation['horizon_label'].lower()}. {recommendation['reason']} "
                f"Suggested risk: **{recommendation['risk_label']}** (like {recommendation['persona']}). "
                "You can change the risk before approving.",
                trace,
                proposal={"id": action_id, "type": "create_account", **recommendation},
            )

        entry = knowledge.match(message)
        if entry:
            trace[0]["action"] = f"detect intent: question ({entry['id']}), route to {', '.join(entry['agents'])}"
            extra: Dict[str, Any] = {"metrics": {}, "sources": [f"Knowledge base: {entry['id']}"], "warnings": []}
            answer = entry["answer"]
            for agent in entry["agents"]:
                if agent == "Macro Signal Agent":
                    trace.append({"agent": agent, "action": "read yield curve and unemployment (Market Data)"})
                    signal = macro.recession_signals()
                    extra["metrics"].update(signal.get("metrics", {}))
                    extra["sources"] += signal.get("sources", [])
                    extra["warnings"] += signal.get("warnings", [])
                    if signal.get("notes"):
                        answer += "\n\n" + "\n".join(f"- {note}" for note in signal["notes"])
                elif agent == "Risk Agent":
                    accounts = store.accounts(user_id)
                    trace.append({"agent": agent, "action": "map exposure to your accounts" if accounts else "no accounts yet"})
                    if accounts:
                        answer += "\n\nYour accounts:\n" + "\n".join(
                            f"- {account['name']} ({account['risk_label']}): handled by {account['horizon_agent']}"
                            + (", shortest horizon, most exposed to a near-term downturn" if account["horizon"] == "short" else "")
                            for account in accounts
                        )
                else:
                    trace.append({"agent": agent, "action": "answer from knowledge base"})
            trace.append({"agent": "Explainability Agent", "action": "attach sources and limits"})
            extra["warnings"].append(DISCLAIMER)
            return self._reply(answer, trace, **extra)
        return self._reply(
            "I don't have that in my knowledge base yet. Try one of these:",
            trace,
            suggestions=knowledge.suggestions() + ["Create a short-term account"],
        )

    def approve(self, action_id: str, risk: str | None = None) -> Dict[str, Any]:
        action = store.PENDING.pop(action_id, None)
        if action is None:
            return self._reply("That proposal has expired.", [])
        payload = dict(action["payload"])
        if risk in PROFILES:
            payload["risk"] = risk
        account = account_creation.create(action["user_id"], payload)
        return self._reply(
            f"Created **{account['name']}** ({account['risk_label']}). It's managed by the "
            f"{account['horizon_agent']} with {', '.join(account['strategies'])} strategies.",
            [
                {"agent": "Governance Agent", "action": "user approved"},
                {"agent": "Account Creation Agent", "action": f"created {account['name']}"},
                {"agent": account["horizon_agent"], "action": f"assigned {', '.join(account['strategies'])}"},
            ],
            warnings=[DISCLAIMER],
        )

    def reject(self, action_id: str) -> Dict[str, Any]:
        store.PENDING.pop(action_id, None)
        return self._reply("No problem, nothing was created.", [{"agent": "Global Orchestrator", "action": "user declined"}])

    @staticmethod
    def _is_create_intent(text: str) -> bool:
        return bool(re.search(r"(create|open|new|start|set up)", text.lower()) and re.search(r"account", text.lower()))

    @staticmethod
    def _reply(answer: str, trace: List[Dict[str, Any]], **kwargs: Any) -> Dict[str, Any]:
        return {
            "answer": answer,
            "trace": trace,
            "metrics": kwargs.get("metrics", {}),
            "sources": kwargs.get("sources", []),
            "warnings": kwargs.get("warnings", []),
            "proposal": kwargs.get("proposal"),
            "suggestions": kwargs.get("suggestions", []),
        }
