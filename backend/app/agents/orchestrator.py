from __future__ import annotations

import re
from typing import Any, Callable, Dict, List
from uuid import uuid4

from app.agents.accounts import RRSPAccountAgent, TFSAAccountAgent
from app.agents.challenge import SuitabilityChallengeAgent, parse_request
from app.agents.explainability import ExplainabilityAgent, registry_from_budget, registry_from_metrics
from app.agents.governance import GovernanceAgent
from app.agents.profile import get_persona
from app.agents import account_creation, knowledge, profile
from app import store
from app.profiles import PROFILES
from app.agents.signals import macro
from app.domain.models import (
    AnalysisRequest,
    AnalysisResponse,
    ChallengeResponse,
    MetricEvidence,
    PerformancePoint,
    TraceStep,
)
from app.domain.presets import PERSONA_SCENARIOS, STRATEGY_HOLDINGS
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

    def challenge(self, persona_id: str, message: str) -> ChallengeResponse:
        """Test an investor-specific request (for example a single stock) against the profile."""
        return SuitabilityChallengeAgent(self.financial_tool, self.explainability_agent).run(
            persona_id, message
        )

    def is_challenge(self, persona_id: str, message: str) -> bool:
        portfolio_value = float(PERSONA_SCENARIOS[persona_id]["portfolio_value"])
        try:
            return parse_request(message, portfolio_value) is not None
        except ValueError:
            return True

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
                "strategy_holdings": {
                    name: STRATEGY_HOLDINGS[name] for name in request.strategy_allocations
                },
            }
        )
        calculation = self.financial_tool("compare_strategy_shift", lambda_payload)
        metrics = [MetricEvidence.model_validate(item) for item in calculation["metrics"]]
        evidence_ids = [metric.evidence_id for metric in metrics]
        robustness = calculation.get("robustness", {})
        trace.append(
            TraceStep(
                step_id="tool.financial_lambda",
                parent_id="account.delegate",
                agent="aws_financial_tools",
                action=(
                    "Calculate current and proposed metrics, replay the 2022 selloff, and "
                    "re-test the conclusion on the full history in AWS Lambda"
                ),
                evidence_ids=evidence_ids,
                details={"aws_request_id": calculation.get("aws_request_id", "unknown")},
            )
        )

        governance = self.governance_agent.evaluate(
            request, calculation["conclusion"], metrics, robustness
        )
        trace.append(
            TraceStep(
                step_id="governance.review",
                parent_id="orchestrator.plan",
                agent=self.governance_agent.name,
                action=(
                    f"Apply simulation, account, evidence, and {persona['name']}'s risk-budget "
                    "controls (loss, recovery, crypto, ESG, robustness)"
                ),
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
            persona_id=request.persona_id,
            robustness=robustness,
        )
        trace.append(
            TraceStep(
                step_id="explainability.synthesize",
                parent_id="governance.review",
                agent=self.explainability_agent.name,
                action="Amazon Bedrock writes digit-free prose; code appends verified figures from the Lambda evidence",
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
            answer_segments=explanation.segments,
            evidence={
                **registry_from_metrics(metrics),
                **registry_from_budget(request.persona_id),
            },
            conclusion=calculation["conclusion"],
            robustness=robustness,
            stress_test=calculation.get("stress_test", {}),
            portfolio_value=request.portfolio_value,
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
            limitations=list(dict.fromkeys([*calculation["limitations"], *explanation.limitations])),
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
            trace.append({"agent": "Approval Gate", "action": "hold the proposal; nothing is created until the user approves"})
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
            routes = entry.get("routes", [])
            trace[0]["action"] = f"detect intent: question ({entry['id']})"
            trace.append({"agent": "Knowledge Base", "action": f"curated answer '{entry['id']}' (static, reviewed text)"})
            extra: Dict[str, Any] = {"metrics": {}, "sources": [f"Knowledge base: {entry['id']}"], "warnings": []}
            answer = entry["answer"]
            if "macro_signals" in routes:
                trace.append({"agent": "Macro Signal Agent", "action": "read yield curves and unemployment from macro_rates.csv"})
                signal = macro.recession_signals()
                extra["metrics"].update(signal.get("metrics", {}))
                extra["sources"] += signal.get("sources", [])
                extra["warnings"] += signal.get("warnings", [])
                if signal.get("notes"):
                    answer += "\n\n" + "\n".join(f"- {note}" for note in signal["notes"])
            if "account_exposure" in routes:
                accounts = store.accounts(user_id)
                trace.append({
                    "agent": "Account Exposure Check",
                    "action": "map the topic to your simulated accounts" if accounts else "no simulated accounts yet",
                })
                if accounts:
                    answer += "\n\nYour accounts:\n" + "\n".join(
                        f"- {account['name']} ({account['risk_label']}, {account['horizon_profile'].lower()})"
                        + (": shortest horizon, most exposed to a near-term downturn" if account["horizon"] == "short" else "")
                        for account in accounts
                    )
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
            f"Created **{account['name']}** ({account['risk_label']}, {account['horizon_profile'].lower()}) "
            f"with {', '.join(account['strategies'])} strategies.",
            [
                {"agent": "Approval Gate", "action": "user approved"},
                {"agent": "Account Creation Agent", "action": f"created {account['name']} with {', '.join(account['strategies'])}"},
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
