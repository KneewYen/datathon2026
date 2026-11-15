from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List
from uuid import uuid4

from app.agents.accounts import RRSPAccountAgent, TFSAAccountAgent
from app.agents.explainability import ExplainabilityAgent
from app.agents.governance import GovernanceAgent
from app.agents.profile import get_persona
from app.agents.intent import parse_investment_intent
from app.agents import account_creation, knowledge, profile
from app import store
from app.profiles import PROFILES
from app.agents.signals import macro
from app.domain.models import (
    AccountOption,
    AnalysisRequest,
    AnalysisResponse,
    EvidenceRecord,
    ExecutionEvent,
    InvestmentAnalysisRequest,
    InvestmentAnalysisResponse,
    MetricEvidence,
    PerformancePoint,
    ResearchResult,
    TraceStep,
)
from app.domain.presets import STRATEGY_HOLDINGS
from app.investors import etf_constituent_fixture, get_investor
from app.services.lambda_tools import invoke
from app.services.research import ResearchProvider, UnavailableResearchProvider

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
        research_provider: ResearchProvider | None = None,
    ):
        self.financial_tool = financial_tool
        self.explainability_agent = explainability_agent or ExplainabilityAgent()
        self.governance_agent = GovernanceAgent()
        self.research_provider = research_provider or UnavailableResearchProvider()

    @staticmethod
    def _execution_event(
        request_id: str,
        event_id: str,
        kind: str,
        agent: str,
        input_summary: str,
        output_summary: str,
        parent_id: str | None = None,
        tool_name: str | None = None,
        evidence_ids: list[str] | None = None,
        status: str = "completed",
        error: str | None = None,
        started_at: datetime | None = None,
    ) -> ExecutionEvent:
        return ExecutionEvent(
            event_id=event_id,
            parent_id=parent_id,
            request_id=request_id,
            kind=kind,
            agent=agent,
            tool_name=tool_name,
            started_at=started_at or datetime.now(timezone.utc),
            ended_at=datetime.now(timezone.utc),
            status=status,
            evidence_ids=evidence_ids or [],
            input_summary=input_summary,
            output_summary=output_summary,
            error=error,
        )

    def analyze_investment(
        self, request: InvestmentAnalysisRequest
    ) -> InvestmentAnalysisResponse:
        request_id = str(uuid4())
        fixture = get_investor(request.investor_id)
        investor = fixture["investor"]
        accounts = fixture["accounts"]
        trace: list[ExecutionEvent] = []
        root_started = datetime.now(timezone.utc)
        intent, clarification = parse_investment_intent(request.question, accounts)
        trace.append(
            self._execution_event(
                request_id,
                "orchestrator.intent",
                "orchestrator",
                "global_orchestrator",
                "Parse the question into a supported investment operation.",
                clarification or f"Parsed a {intent.currency} purchase of {intent.ticker}.",
                status="blocked" if clarification else "completed",
                started_at=root_started,
            )
        )
        if intent is None:
            return InvestmentAnalysisResponse(
                request_id=request_id,
                status="clarification_required",
                question=request.question,
                clarification=clarification,
                investor=investor,
                accounts=accounts,
                research=ResearchResult(
                    status="unavailable",
                    provider="not-invoked",
                    retrieved_at=datetime.now(timezone.utc),
                    limitations=[
                        "Research was not attempted because the investment request needs clarification."
                    ],
                ),
                trace=trace,
                answer=clarification or "More information is required.",
                model_id="not-invoked",
            )

        selected_accounts = [
            account
            for account in accounts
            if intent.compare_accounts or account["id"] in intent.account_ids
        ]
        if not selected_accounts:
            selected_accounts = accounts
        common_payload = {
            "analysis_id": request_id,
            "accounts": accounts,
            "target_ticker": intent.ticker,
            "amount": intent.amount,
            "currency": intent.currency,
            "start_date": request.start_date.isoformat(),
            "end_date": request.end_date.isoformat(),
            "etf_constituents": etf_constituent_fixture(),
        }
        tool_cache: dict[str, dict] = {}
        research = None
        account_findings: dict[str, list] = {}

        for account in selected_accounts:
            account_agent = ACCOUNT_AGENTS[account["type"]]()
            account_event_id = f"account.{account['id']}"
            account_started = datetime.now(timezone.utc)
            account_plan = account_agent.plan(
                {
                    "workflow": "investment_purchase",
                    "ticker": intent.ticker,
                    "account": account,
                }
            )
            strategy_findings = account_agent.delegate_investment(
                account, request.question, intent.ticker
            )
            account_findings[account["id"]] = strategy_findings
            trace.append(
                self._execution_event(
                    request_id,
                    account_event_id,
                    "agent",
                    account_agent.name,
                    f"Load {account['name']} holdings, objective, and constraints.",
                    account_plan.summary,
                    parent_id="orchestrator.intent",
                    started_at=account_started,
                )
            )
            for index, finding in enumerate(strategy_findings, start=1):
                strategy_event_id = f"{account_event_id}.strategy.{index}"
                trace.append(
                    self._execution_event(
                        request_id,
                        strategy_event_id,
                        "agent",
                        finding.agent,
                        f"Assess {intent.ticker} for {account['type']} using typed tools.",
                        finding.summary,
                        parent_id=account_event_id,
                    )
                )
                for operation in finding.requested_operations:
                    cache_key = (
                        f"{operation}:{account['id']}"
                        if operation == "simulate_account_purchase"
                        else operation
                    )
                    tool_event_id = f"{strategy_event_id}.tool.{operation}"
                    started = datetime.now(timezone.utc)
                    if operation == "research_news":
                        if research is None:
                            research = self.research_provider.search_company(intent.ticker)
                        evidence_ids = [
                            item.get("evidence_id")
                            for item in research.items
                            if item.get("evidence_id")
                        ]
                        trace.append(
                            self._execution_event(
                                request_id,
                                tool_event_id,
                                "tool",
                                finding.agent,
                                f"Retrieve approved recent research for {intent.ticker}.",
                                (
                                    f"Research provider returned {len(research.items)} sourced items."
                                    if research.status == "available"
                                    else "No approved live research provider is configured."
                                ),
                                parent_id=strategy_event_id,
                                tool_name="news_research",
                                evidence_ids=evidence_ids,
                                status="completed" if research.status == "available" else "blocked",
                                started_at=started,
                            )
                        )
                        continue
                    if cache_key not in tool_cache:
                        payload = dict(common_payload)
                        if operation == "simulate_account_purchase":
                            payload["account_id"] = account["id"]
                        tool_cache[cache_key] = self.financial_tool(operation, payload)
                        reused = False
                    else:
                        reused = True
                    result = tool_cache[cache_key]
                    evidence_ids = [item["evidence_id"] for item in result.get("evidence", [])]
                    trace.append(
                        self._execution_event(
                            request_id,
                            tool_event_id,
                            "tool",
                            finding.agent,
                            f"Run {operation} for {account['type']} with validated fixture and market inputs.",
                            (
                                "Reused the validated result from an earlier delegated call."
                                if reused
                                else f"Completed {operation} and returned {len(evidence_ids)} evidence records."
                            ),
                            parent_id=strategy_event_id,
                            tool_name=operation,
                            evidence_ids=evidence_ids,
                            started_at=started,
                        )
                    )

        if research is None:
            research = self.research_provider.search_company(intent.ticker)
        holdings_result = tool_cache.get("analyze_holdings_exposure")
        market_result = tool_cache.get("market_snapshot")
        simulation_results = [
            tool_cache[f"simulate_account_purchase:{account['id']}"]
            for account in selected_accounts
            if f"simulate_account_purchase:{account['id']}" in tool_cache
        ]
        if holdings_result is None:
            holdings_result = self.financial_tool("analyze_holdings_exposure", common_payload)
        if market_result is None:
            market_result = {
                "evidence": [],
                "limitations": [
                    "The momentum agent was not activated for the selected account, so no market-trend tool was run."
                ],
            }

        evidence_payloads = [
            *holdings_result.get("evidence", []),
            *market_result.get("evidence", []),
            *[
                item
                for result in simulation_results
                for item in result.get("evidence", [])
            ],
        ]
        for item in research.items:
            if item.get("evidence_id"):
                evidence_payloads.append(item)
        evidence_by_id = {item["evidence_id"]: item for item in evidence_payloads}
        evidence = [EvidenceRecord.model_validate(item) for item in evidence_by_id.values()]
        options = []
        for result in simulation_results:
            option_payload = dict(result["option"])
            option_payload["strategy_findings"] = account_findings[option_payload["account_id"]]
            options.append(AccountOption.model_validate(option_payload))
        governance = self.governance_agent.evaluate_investment(
            intent.model_dump(), accounts, [item.model_dump() for item in options], research.status
        )
        governance_evidence = sorted(
            {evidence_id for finding in governance for evidence_id in finding.evidence_ids}
        )
        trace.append(
            self._execution_event(
                request_id,
                "governance.review",
                "governance",
                self.governance_agent.name,
                "Apply account constraints, data-quality checks, and simulation boundaries.",
                f"Applied {len(governance)} deterministic governance findings.",
                parent_id="orchestrator.intent",
                evidence_ids=governance_evidence,
            )
        )
        limitations = list(
            dict.fromkeys(
                [
                    *holdings_result.get("limitations", []),
                    *market_result.get("limitations", []),
                    *[item for result in simulation_results for item in result.get("limitations", [])],
                    *research.limitations,
                ]
            )
        )
        explanation_started = datetime.now(timezone.utc)
        explanation = self.explainability_agent.explain_investment(
            request.question,
            evidence,
            governance,
            [item.model_dump() for item in options],
            limitations,
        )
        trace.append(
            self._execution_event(
                request_id,
                "orchestrator.synthesis",
                "explainability",
                self.explainability_agent.name,
                "Synthesize only the validated tool evidence and governance findings.",
                "Produced a grounded cross-account explanation.",
                parent_id="orchestrator.intent",
                evidence_ids=explanation.evidence_ids,
                started_at=explanation_started,
            )
        )
        assumptions = list(
            dict.fromkeys(
                item
                for result in simulation_results
                for item in result.get("assumptions", [])
            )
        )
        return InvestmentAnalysisResponse(
            request_id=request_id,
            status="completed",
            question=request.question,
            intent=intent,
            investor=investor,
            accounts=accounts,
            current_exposure=holdings_result["portfolio"],
            account_options=options,
            governance=governance,
            research=research,
            evidence=evidence,
            trace=trace,
            answer=explanation.answer,
            assumptions=assumptions,
            limitations=[*limitations, *explanation.limitations],
            model_id=explanation.model_id,
        )

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
