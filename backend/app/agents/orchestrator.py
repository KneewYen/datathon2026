from __future__ import annotations

from typing import Callable, Dict
from uuid import uuid4

from app.agents.accounts import RRSPAccountAgent, TFSAAccountAgent
from app.agents.explainability import ExplainabilityAgent
from app.agents.governance import GovernanceAgent
from app.agents.profile import get_persona
from app.domain.models import (
    AnalysisRequest,
    AnalysisResponse,
    MetricEvidence,
    PerformancePoint,
    TraceStep,
)
from app.domain.presets import STRATEGY_HOLDINGS
from app.services.lambda_tools import invoke


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
