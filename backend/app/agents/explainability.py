"""Evidence registry, grounded Bedrock synthesis, and verified-number rendering.

Bedrock never writes a digit. It may reference a verified figure only through a
``{{token}}`` placeholder drawn from the registry below; the backend substitutes the
Lambda-calculated value and keeps the link to its evidence for the UI.
"""

from __future__ import annotations

import re
from typing import Any, Callable, Dict, Iterable, List, Optional

from app.domain.models import Explanation, GovernanceFinding, MetricEvidence
from app.domain.presets import PERSONAS
from app.services.bedrock import TOKEN_PATTERN, synthesize

BUDGET_SOURCE = "PortfolioGuard fictional persona risk budget (backend/app/domain/presets.py)"
BUDGET_UNITS = {
    "max_stress_drawdown": ("Loss budget in a 2022-style selloff", "percent"),
    "single_position_cap": ("Single-company cap", "percent"),
    "crypto_cap": ("Crypto cap", "percent"),
    "max_months_underwater": ("Longest acceptable recovery", "months"),
}


def format_value(value: Optional[float], unit: str, signed: bool = False) -> str:
    if value is None:
        return "not recovered by the end of the data" if unit == "months" else "unavailable"
    if unit == "percent":
        return f"{value * 100:+.1f} pts" if signed else f"{value * 100:.1f}%"
    if unit == "months":
        return f"{value:+.0f} months" if signed else f"{value:.0f} months"
    if unit == "cad":
        sign = "-" if value < 0 else ("+" if signed else "")
        return f"{sign}${abs(value):,.0f}"
    return f"{value:+.3f}" if signed else f"{value:.3f}"


def _entry(token: str, evidence_id: str, label: str, value: Optional[float], unit: str,
           source: str, formula_version: str, role: str, signed: bool = False) -> Dict[str, Any]:
    return {
        "token": token,
        "evidence_id": evidence_id,
        "label": label,
        "role": role,
        "value": value,
        "unit": unit,
        "display": format_value(value, unit, signed),
        "source": source,
        "formula_version": formula_version,
    }


def registry_from_metrics(metrics: Iterable[MetricEvidence]) -> Dict[str, Dict[str, Any]]:
    registry: Dict[str, Dict[str, Any]] = {}
    for metric in metrics:
        for role, value, signed in (
            ("current", metric.current, False),
            ("proposed", metric.proposed, False),
            ("delta", metric.delta, True),
        ):
            token = f"{metric.evidence_id}.{role}"
            registry[token] = _entry(token, metric.evidence_id, metric.label, value, metric.unit,
                                     metric.source, metric.formula_version, role, signed)
    return registry


def registry_from_scenarios(scenarios: Iterable[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    registry: Dict[str, Dict[str, Any]] = {}
    for scenario in scenarios:
        for item in scenario["evidence"]:
            token = item["evidence_id"]
            registry[token] = _entry(token, token, item["label"], item["value"], item["unit"],
                                     item["source"], item["formula_version"], scenario["label"])
    return registry


def registry_from_budget(persona_id: str) -> Dict[str, Dict[str, Any]]:
    budget = PERSONAS[persona_id]["risk_budget"]
    registry = {}
    for key, (label, unit) in BUDGET_UNITS.items():
        token = f"budget.{key}"
        registry[token] = _entry(token, token, label, float(budget[key]), unit, BUDGET_SOURCE,
                                 "persona-budget-v1", PERSONAS[persona_id]["name"])
    return registry


def render(template: str, registry: Dict[str, Dict[str, Any]]) -> tuple[str, List[Dict[str, Any]]]:
    """Substitute verified values for tokens; return plain text and UI segments."""
    segments: List[Dict[str, Any]] = []
    position = 0
    for match in TOKEN_PATTERN.finditer(template):
        if match.start() > position:
            segments.append({"type": "text", "text": template[position:match.start()]})
        entry = registry[match.group(1)]
        segments.append({"type": "evidence", "text": entry["display"], "token": entry["token"]})
        position = match.end()
    if position < len(template):
        segments.append({"type": "text", "text": template[position:]})
    return "".join(segment["text"] for segment in segments), segments


def direction(before: Optional[float], after: Optional[float], metric: str = "") -> str:
    """Describe a change in plain risk language so negative drawdowns cannot be misread."""
    if before is None or after is None:
        return "not recovered by the end of the data" if "months" in metric else "unavailable"
    if abs(after - before) < 1e-12:
        return "unchanged"
    if "drawdown" in metric or "loss" in metric:
        return "larger loss" if after < before else "smaller loss"
    if "months" in metric:
        return "longer recovery" if after > before else "shorter recovery"
    return "higher" if after > before else "lower"


def scrub_digits(text: str) -> str:
    """Hide raw numbers from the model so it cites tokens instead of copying digits."""
    return re.sub(r"[-+$]?\d[\d,.]*\s*%?", "[see evidence]", text)


class ExplainabilityAgent:
    name = "explainability_agent"

    def __init__(self, synthesizer: Callable[[Dict], Dict] = synthesize):
        self.synthesizer = synthesizer

    def synthesize_packet(
        self,
        packet: Dict[str, Any],
        registry: Dict[str, Dict[str, Any]],
        allowed_evidence_ids: List[str],
        figures_template: str = "",
    ) -> Explanation:
        """Bedrock writes digit-free prose; verified figures are appended from the registry."""
        packet = {
            **packet,
            "allowed_evidence_ids": allowed_evidence_ids,
            "allowed_literals": ["2022"],
        }
        result = self.synthesizer(packet)
        template = result["answer"]
        if figures_template:
            template = f"{template}\n\n{figures_template}"
        answer, segments = render(template, registry)
        return Explanation.model_validate(
            {**result, "answer": answer, "answer_template": template, "segments": segments}
        )
    def explain(
        self,
        question: str,
        conclusion: str,
        metrics: list[MetricEvidence],
        governance: list[GovernanceFinding],
        assumptions: list[str],
        limitations: list[str],
        persona_id: str = "amira",
        robustness: Optional[Dict[str, Any]] = None,
    ) -> Explanation:
        registry = {**registry_from_metrics(metrics), **registry_from_budget(persona_id)}
        persona = PERSONAS[persona_id]
        packet = {
            "question": question,
            "investor": {
                "name": persona["name"],
                "risk": persona["risk"],
                "horizon_years": persona["horizon_years"],
                "objective": persona["objective"],
                "preferences": persona["preferences"],
            },
            "conclusion": conclusion,
            "robust_across_windows": (robustness or {}).get("consistent"),

            "metrics": [
                {
                    "evidence_id": metric.evidence_id,
                    "label": metric.label,
                    "proposed_vs_current": direction(metric.current, metric.proposed, metric.evidence_id),
                }
                for metric in metrics
            ],
            "governance": [
                {"rule_id": finding.rule_id, "severity": finding.severity, "message": scrub_digits(finding.message)}
                for finding in governance
            ],
            "assumptions": [scrub_digits(item) for item in assumptions],
            "limitations": limitations,
        }
        return self.synthesize_packet(
            packet, registry, [metric.evidence_id for metric in metrics], analysis_figures(registry)
        )


def analysis_figures(registry: Dict[str, Dict[str, Any]]) -> str:
    def pair(evidence_id: str, label: str) -> str:
        return f"{label} {{{{{evidence_id}.current}}}} to {{{{{evidence_id}.proposed}}}}"

    parts = [
        pair("metric.annualized_volatility", "annualized volatility"),
        pair("metric.maximum_drawdown", "maximum drawdown"),
        pair("metric.annualized_return", "historical annualized return"),
    ]
    if "metric.stress_2022_drawdown.proposed" in registry:
        stress = "in the 2022 replay the proposed portfolio fell {{metric.stress_2022_drawdown.proposed}}"
        if "metric.stress_2022_loss_cad.proposed" in registry:
            stress += " ({{metric.stress_2022_loss_cad.proposed}} on the fictional balance)"
        parts.append(stress + " against a {{budget.max_stress_drawdown}} loss budget")
    if "metric.months_underwater.proposed" in registry:
        parts.append(pair("metric.months_underwater", "time from the pre-2022 peak to recovery"))
    return "Verified figures (current to proposed): " + "; ".join(parts) + "."
