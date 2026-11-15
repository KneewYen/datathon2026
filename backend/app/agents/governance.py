"""Deterministic governance checks for suitability conflicts and safe boundaries."""

from __future__ import annotations

from typing import Any, Dict, Mapping, Optional

from app.domain.models import AnalysisRequest, GovernanceFinding, MetricEvidence
from app.domain.presets import PERSONAS
from app.domain.universe import UNIVERSE_SOURCE, assets, asset_weights, crypto_weight, holdings_in_sectors

NEAR_LIMIT_UTILIZATION = 0.9


def _pct(value: float) -> str:
    return f"{value * 100:.1f}%"


def profile_controls(
    persona_id: str,
    weights: Mapping[str, float],
    stress_drawdown: Optional[float],
    months_underwater: Optional[float],
    evidence: Mapping[str, str],
    include_passes: bool = True,
    focus_ticker: Optional[str] = None,
) -> list[GovernanceFinding]:
    """Persona risk-budget controls shared by the scenario analysis and the challenge flow.

    ``evidence`` maps a control input (stress_drawdown, months_underwater, largest_position)
    to the evidence ID that supports it. The single-company cap applies to ``focus_ticker``,
    the asset an investor asked for; diversified baskets are covered by the HHI control.
    """
    persona = PERSONAS[persona_id]
    budget = persona["risk_budget"]
    name = persona["name"]
    findings: list[GovernanceFinding] = []

    crypto = crypto_weight(weights)
    if crypto > budget["crypto_cap"] + 1e-9:
        if budget["crypto_cap"] == 0:
            findings.append(GovernanceFinding(
                rule_id="CRYPTO_OUTSIDE_PROFILE",
                severity="warning",
                message=f"{name}'s fictional profile excludes crypto assets; this allocation holds {_pct(crypto)}.",
            ))
        else:
            findings.append(GovernanceFinding(
                rule_id="CRYPTO_CAP_EXCEEDED",
                severity="warning",
                message=(
                    f"Crypto exposure of {_pct(crypto)} exceeds {name}'s {_pct(budget['crypto_cap'])} cap. "
                    "High risk tolerance does not mean any position size is acceptable."
                ),
            ))

    excluded_sectors = persona["esg_excluded_sectors"]
    if excluded_sectors:
        excluded = holdings_in_sectors(weights, excluded_sectors)
        if excluded:
            findings.append(GovernanceFinding(
                rule_id="ESG_EXCLUSION_CONFLICT",
                severity="warning",
                message=(
                    f"Holds {', '.join(sorted(excluded))} in an excluded sector ({', '.join(excluded_sectors)}), "
                    f"which conflicts with {name}'s ESG preference. Sector source: {UNIVERSE_SOURCE}."
                ),
            ))
        elif include_passes:
            findings.append(GovernanceFinding(
                rule_id="ESG_SCREEN_PASSED",
                severity="info",
                message=f"No holdings in excluded sectors ({', '.join(excluded_sectors)}) per {UNIVERSE_SOURCE}.",
            ))

    if focus_ticker and assets().get(focus_ticker, {}).get("asset_class") == "equity":
        position = weights.get(focus_ticker, 0.0)
        if position > budget["single_position_cap"] + 1e-9:
            findings.append(GovernanceFinding(
                rule_id="SINGLE_POSITION_CAP",
                severity="warning",
                message=(
                    f"{focus_ticker} would be {_pct(position)} of the portfolio, above {name}'s "
                    f"{_pct(budget['single_position_cap'])} single-company cap."
                ),
                evidence_ids=[evidence["largest_position"]] if "largest_position" in evidence else [],
            ))

    if stress_drawdown is not None:
        limit = budget["max_stress_drawdown"]
        stress_ids = [evidence["stress_drawdown"]] if "stress_drawdown" in evidence else []
        if stress_drawdown < limit:
            findings.append(GovernanceFinding(
                rule_id="STRESS_BUDGET_EXCEEDED",
                severity="warning",
                message=(
                    f"Replaying 2022, this allocation fell {_pct(stress_drawdown)}, beyond {name}'s "
                    f"{_pct(limit)} loss budget."
                ),
                evidence_ids=stress_ids,
            ))
        elif stress_drawdown <= limit * NEAR_LIMIT_UTILIZATION:
            findings.append(GovernanceFinding(
                rule_id="STRESS_BUDGET_NEAR_LIMIT",
                severity="warning",
                message=(
                    f"Replaying 2022, this allocation fell {_pct(stress_drawdown)}, close to {name}'s "
                    f"{_pct(limit)} loss budget."
                ),
                evidence_ids=stress_ids,
            ))
        elif include_passes:
            findings.append(GovernanceFinding(
                rule_id="STRESS_BUDGET_RESPECTED",
                severity="info",
                message=f"The 2022 replay stays within {name}'s {_pct(limit)} loss budget.",
                evidence_ids=stress_ids,
            ))

    recovery_ids = [evidence["months_underwater"]] if "months_underwater" in evidence else []
    max_months = budget["max_months_underwater"]
    if stress_drawdown is not None and months_underwater is None:
        findings.append(GovernanceFinding(
            rule_id="RECOVERY_NOT_OBSERVED",
            severity="warning",
            message="After the 2022 trough this allocation had not regained its prior peak by the end of the data.",
            evidence_ids=recovery_ids,
        ))
    elif months_underwater is not None and months_underwater > max_months:
        findings.append(GovernanceFinding(
            rule_id="RECOVERY_EXCEEDS_HORIZON",
            severity="warning",
            message=(
                f"Recovering from 2022 took {months_underwater:.0f} months, longer than the {max_months} months "
                f"that fit comfortably inside {name}'s {persona['horizon_years']}-year horizon."
            ),
            evidence_ids=recovery_ids,
        ))
    return findings


class GovernanceAgent:
    name = "governance_agent"

    @staticmethod
    def _proposed_allocations(request: AnalysisRequest) -> dict[str, float]:
        proposed = dict(request.strategy_allocations)
        proposed[request.shift.from_strategy] -= request.shift.amount
        proposed[request.shift.to_strategy] += request.shift.amount
        return proposed

    def evaluate(
        self,
        request: AnalysisRequest,
        conclusion: str,
        metrics: list[MetricEvidence],
        robustness: Optional[Dict[str, Any]] = None,
    ) -> list[GovernanceFinding]:
        metric_map = {metric.evidence_id: metric for metric in metrics}
        proposed = self._proposed_allocations(request)
        findings = [
            GovernanceFinding(
                rule_id="SIMULATION_ONLY",
                severity="info",
                message=(
                    "This analysis compares fictional portfolios and cannot execute a trade."
                ),
            )
        ]

        if request.account_type == "TFSA":
            findings.append(
                GovernanceFinding(
                    rule_id="TFSA_SCOPE_LIMIT",
                    severity="info",
                    message=(
                        "The scenario does not determine TFSA eligibility, contribution room, "
                        "or tax consequences."
                    ),
                )
            )
        else:
            findings.append(
                GovernanceFinding(
                    rule_id="RRSP_SCOPE_LIMIT",
                    severity="info",
                    message=(
                        "The scenario does not calculate RRSP deduction eligibility, "
                        "withdrawal taxation, or personal tax outcomes."
                    ),
                )
            )

        if conclusion == "risk_reduced":
            findings.append(
                GovernanceFinding(
                    rule_id="RISK_REDUCTION_SUPPORTED",
                    severity="info",
                    message=(
                        "Both annualized volatility and historical maximum drawdown improved "
                        "under the stated methodology."
                    ),
                    evidence_ids=[
                        "metric.annualized_volatility",
                        "metric.maximum_drawdown",
                    ],
                )
            )
        elif conclusion == "mixed":
            findings.append(
                GovernanceFinding(
                    rule_id="MIXED_RISK_EVIDENCE",
                    severity="warning",
                    message="The risk indicators do not move in the same direction.",
                    evidence_ids=[
                        "metric.annualized_volatility",
                        "metric.maximum_drawdown",
                    ],
                )
            )
        else:
            findings.append(
                GovernanceFinding(
                    rule_id="RISK_NOT_REDUCED",
                    severity="warning",
                    message="The proposed shift does not reduce the measured historical risk.",
                    evidence_ids=[
                        "metric.annualized_volatility",
                        "metric.maximum_drawdown",
                    ],
                )
            )

        return_metric = metric_map.get("metric.annualized_return")
        if return_metric and return_metric.delta < 0:
            findings.append(
                GovernanceFinding(
                    rule_id="RETURN_TRADEOFF",
                    severity="info",
                    message=(
                        "The lower measured risk is accompanied by a lower historical annualized return."
                    ),
                    evidence_ids=["metric.annualized_return"],
                )
            )

        if request.persona_id == "mateo":
            findings.append(
                GovernanceFinding(
                    rule_id="ESG_EVIDENCE_UNAVAILABLE",
                    severity="warning",
                    message=(
                        "A sector-based ESG screen is applied, but the starter dataset cannot verify "
                        "company-level environmental or social controversies."
                    ),
                )
            )

        concentration_metric = metric_map.get("metric.concentration_hhi")
        if (
            request.persona_id == "amira"
            and concentration_metric
            and concentration_metric.proposed > 0.18
        ):
            findings.append(
                GovernanceFinding(
                    rule_id="CONCENTRATION_CONTROL",
                    severity="warning",
                    message=(
                        "The proposed portfolio remains concentrated despite Amira's "
                        "high risk tolerance; diversification controls still apply."
                    ),
                    evidence_ids=["metric.concentration_hhi"],
                )
            )

        if request.persona_id == "mateo" and (
            proposed.get("growth", 0.0) + proposed.get("momentum", 0.0) > 0.60
        ):
            findings.append(
                GovernanceFinding(
                    rule_id="MODERATE_PROFILE_CONFLICT",
                    severity="warning",
                    message=(
                        "The proposed growth and momentum exposure conflicts with Mateo's "
                        "moderate fictional risk profile."
                    ),
                )
            )

        if request.persona_id == "robert" and (
            proposed.get("growth", 0.0) + proposed.get("momentum", 0.0) > 0.40
            or proposed.get("preservation", 0.0) < 0.25
        ):
            findings.append(
                GovernanceFinding(
                    rule_id="SHORT_HORIZON_PROFILE_CONFLICT",
                    severity="warning",
                    message=(
                        "The proposed allocation conflicts with Robert's short fictional "
                        "horizon and capital-preservation objective."
                    ),
                    evidence_ids=[
                        evidence_id
                        for evidence_id in (
                            "metric.annualized_volatility",
                            "metric.maximum_drawdown",
                        )
                        if evidence_id in metric_map
                    ],
                )
            )

        stress = metric_map.get("metric.stress_2022_drawdown")
        recovery = metric_map.get("metric.months_underwater")
        findings.extend(
            profile_controls(
                request.persona_id,
                asset_weights(proposed),
                stress.proposed if stress else None,
                recovery.proposed if recovery else None,
                {
                    "stress_drawdown": "metric.stress_2022_drawdown",
                    "months_underwater": "metric.months_underwater",
                },
            )
        )

        if robustness and robustness.get("windows"):
            labels = ", ".join(window["label"] for window in robustness["windows"])
            if robustness.get("consistent"):
                findings.append(
                    GovernanceFinding(
                        rule_id="CONCLUSION_ROBUST",
                        severity="info",
                        message=f"The risk conclusion is the same in every tested window ({labels}).",
                        evidence_ids=[
                            evidence_id
                            for evidence_id in ("metric.full_history_volatility", "metric.full_history_drawdown")
                            if evidence_id in metric_map
                        ],
                    )
                )
            else:
                findings.append(
                    GovernanceFinding(
                        rule_id="WINDOW_SENSITIVE",
                        severity="warning",
                        message=f"The risk conclusion changes between windows ({labels}); treat it as fragile.",
                        evidence_ids=[
                            evidence_id
                            for evidence_id in ("metric.full_history_volatility", "metric.full_history_drawdown")
                            if evidence_id in metric_map
                        ],
                    )
                )
        return findings
