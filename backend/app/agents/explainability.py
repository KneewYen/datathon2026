"""Evidence-packet construction and grounded Bedrock explanation synthesis."""

from __future__ import annotations

from typing import Callable, Dict

from app.domain.models import EvidenceRecord, Explanation, GovernanceFinding, MetricEvidence
from app.services.bedrock import synthesize


class ExplainabilityAgent:
    name = "explainability_agent"

    def __init__(self, synthesizer: Callable[[Dict], Dict] = synthesize):
        self.synthesizer = synthesizer

    def explain(
        self,
        question: str,
        conclusion: str,
        metrics: list[MetricEvidence],
        governance: list[GovernanceFinding],
        assumptions: list[str],
        limitations: list[str],
    ) -> Explanation:
        allowed_ids = [metric.evidence_id for metric in metrics]
        packet = {
            "question": question,
            "conclusion": conclusion,
            "metrics": [metric.model_dump() for metric in metrics],
            "governance": [finding.model_dump() for finding in governance],
            "assumptions": assumptions,
            "limitations": limitations,
            "allowed_evidence_ids": allowed_ids,
        }
        return Explanation.model_validate(self.synthesizer(packet))

    def explain_investment(
        self,
        question: str,
        evidence: list[EvidenceRecord],
        governance: list[GovernanceFinding],
        account_options: list[dict],
        limitations: list[str],
    ) -> Explanation:
        allowed_ids = [item.evidence_id for item in evidence]
        packet = {
            "question": question,
            "workflow": "cross_account_investment_purchase",
            "verified_evidence": [item.model_dump() for item in evidence],
            "account_options": account_options,
            "governance": [finding.model_dump() for finding in governance],
            "limitations": limitations,
            "allowed_evidence_ids": allowed_ids,
            "instruction": (
                "Compare account suitability and explain the material trade-offs without "
                "introducing any new numbers or implying that a trade will be executed."
            ),
        }
        return Explanation.model_validate(self.synthesizer(packet))
