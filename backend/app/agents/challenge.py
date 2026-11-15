"""Suitability Challenge Agent: tests a specific investor request against the profile.

The agent does not simply agree. It builds the requested allocation alongside a capped
version and a profile-aligned alternative, has Lambda measure all of them on the same
data, applies the persona's risk budget, and selects the closest scenario that fits.
"""

from __future__ import annotations

import re
from typing import Any, Callable, Dict, List, Optional
from uuid import uuid4

from app.agents.explainability import (
    ExplainabilityAgent,
    _entry,
    direction,
    registry_from_budget,
    registry_from_scenarios,
    scrub_digits,
)
from app.agents.governance import profile_controls
from app.domain.models import ChallengeResponse, GovernanceFinding, ScenarioResult, TraceStep
from app.domain.presets import CHALLENGE_BASELINES, PERSONA_SCENARIOS, PERSONAS, STRATEGY_LABELS
from app.domain.universe import UNIVERSE_SOURCE, asset_weights, assets, holdings_for, single_strategy

DEFAULT_WEIGHT = 0.10
MIN_CAPPED_WEIGHT = 0.01
# Warnings that flag proximity to a limit without breaching it.
CAUTION_ONLY_RULES = {"STRESS_BUDGET_NEAR_LIMIT"}
ALIASES = {
    "bitcoin": "BTC-USD",
    "btc": "BTC-USD",
    "ethereum": "ETH-USD",
    "ether": "ETH-USD",
    "eth": "ETH-USD",
    "nvidia": "NVDA",
    "tesla": "TSLA",
    "apple": "AAPL",
    "microsoft": "MSFT",
    "amazon": "AMZN",
    "google": "GOOGL",
    "alphabet": "GOOGL",
    "exxon": "XOM",
    "jpmorgan": "JPM",
    "johnson & johnson": "JNJ",
    "procter": "PG",
    "shopify": "SHOP.TO",
    "enbridge": "ENB.TO",
    "royal bank": "RY.TO",
    "toronto-dominion": "TD.TO",
    "manulife": "MFC.TO",
    "canadian natural": "CNQ.TO",
    "canadian national": "CNR.TO",
    "cn rail": "CNR.TO",
    "fortis": "FTS.TO",
    "couche-tard": "ATD.TO",
    "constellation": "CSU.TO",
    "gold": "GLD",
}
CHALLENGE_METRICS = (
    "annualized_volatility",
    "maximum_drawdown",
    "annualized_return",
    "stress_2022_drawdown",
    "months_underwater",
    "largest_position",
    "focus_position",
)


def parse_request(message: str, portfolio_value: float) -> Optional[Dict[str, Any]]:
    """Deterministically extract the asset and position size from a free-text request."""
    lowered = message.lower()
    ticker = None
    for alias, symbol in ALIASES.items():
        if re.search(rf"(?<![a-z]){re.escape(alias)}(?![a-z])", lowered):
            ticker = symbol
            break
    if ticker is None:
        for symbol in assets():
            base = re.split(r"[.\-]", symbol)[0]
            if len(base) >= 2 and re.search(rf"(?<![A-Za-z]){re.escape(base)}(?![A-Za-z])", message):
                ticker = symbol
                break
    if ticker is None:
        return None

    weight, weight_source = DEFAULT_WEIGHT, "assumed"
    percent = re.search(r"(\d+(?:\.\d+)?)\s*(?:%|percent|per cent)", lowered)
    dollars = re.search(r"\$\s?(\d[\d,]*(?:\.\d+)?)\s*(k|thousand)?", lowered)
    if percent:
        weight, weight_source = float(percent.group(1)) / 100, "stated"
    elif dollars:
        amount = float(dollars.group(1).replace(",", "")) * (1000 if dollars.group(2) else 1)
        weight, weight_source = amount / portfolio_value, "stated_amount"
    if not 0 < weight < 1:
        raise ValueError("the requested position must be between 0% and 100% of the portfolio")

    asset = assets()[ticker]
    return {
        "ticker": ticker,
        "name": asset["name"],
        "asset_class": asset["asset_class"],
        "sector": asset["sector"],
        "weight": weight,
        "weight_source": weight_source,
    }


def with_position(base: Dict[str, float], strategy: str, weight: float) -> Dict[str, float]:
    allocation = {name: value * (1 - weight) for name, value in base.items()}
    allocation[strategy] = allocation.get(strategy, 0.0) + weight
    return {name: round(value, 12) for name, value in allocation.items() if value > 1e-12}


class SuitabilityChallengeAgent:
    name = "suitability_challenge_agent"

    def __init__(
        self,
        financial_tool: Callable[[str, Dict], Dict],
        explainability_agent: ExplainabilityAgent,
    ):
        self.financial_tool = financial_tool
        self.explainability_agent = explainability_agent

    def _cap_weight(self, persona_id: str, request: Dict[str, Any], baseline: Dict[str, float]) -> float:
        persona = PERSONAS[persona_id]
        budget = persona["risk_budget"]
        if request["sector"] in persona["esg_excluded_sectors"]:
            return 0.0
        weights = asset_weights(baseline)
        if request["asset_class"] == "crypto":
            cap = budget["crypto_cap"]
            existing = sum(w for t, w in weights.items() if assets()[t]["asset_class"] == "crypto")
        elif request["asset_class"] == "equity":
            cap = budget["single_position_cap"]
            existing = weights.get(request["ticker"], 0.0)
        else:
            return request["weight"]
        # Solve existing * (1 - w) + w = cap for the extra weight w.
        return max(0.0, (cap - existing) / (1 - existing)) if existing < 1 else 0.0

    def build_scenarios(self, persona_id: str, request: Dict[str, Any]) -> List[Dict[str, Any]]:
        persona = PERSONAS[persona_id]
        baseline_config = CHALLENGE_BASELINES[persona_id]
        baseline = {
            name: value
            for name, value in baseline_config["strategy_allocations"].items()
            if value > 0
        }
        ticker, weight = request["ticker"], request["weight"]
        position = single_strategy(ticker)
        scenarios = [
            {
                "id": "baseline",
                "label": "Current portfolio",
                "description": baseline_config["description"],
                "strategy_allocations": baseline,
            },
            {
                "id": "requested",
                "label": f"As requested: add {weight:.0%} {ticker}",
                "description": f"Adds {ticker} at {weight:.1%}, funded proportionally from every sleeve.",
                "strategy_allocations": with_position(baseline, position, weight),
            },
        ]
        cap_weight = self._cap_weight(persona_id, request, baseline)
        if MIN_CAPPED_WEIGHT <= cap_weight < weight - 1e-9:
            scenarios.append({
                "id": "capped",
                "label": f"Capped: add {cap_weight:.1%} {ticker}",
                "description": (
                    f"Keeps the idea but adds only {cap_weight:.1%} {ticker}, the most {persona['name']}'s "
                    "risk budget allows given what the portfolio already holds."
                ),
                "strategy_allocations": with_position(baseline, position, cap_weight),
            })
        alternative = persona["alternative_strategy"]
        scenarios.append({
            "id": "alternative",
            "label": f"Alternative: add {weight:.0%} {STRATEGY_LABELS[alternative].lower()} basket",
            "description": (
                f"Puts the same amount into the diversified {STRATEGY_LABELS[alternative].lower()} basket "
                f"that matches {persona['name']}'s profile instead of one asset."
            ),
            "strategy_allocations": with_position(baseline, alternative, weight),
        })
        return scenarios

    def run(self, persona_id: str, message: str) -> ChallengeResponse:
        analysis_id = str(uuid4())
        persona = PERSONAS[persona_id]
        scenario_config = PERSONA_SCENARIOS[persona_id]
        portfolio_value = float(scenario_config["portfolio_value"])
        request = parse_request(message, portfolio_value)
        if request is None:
            raise ValueError(
                "No asset from the starter universe was found in the request. "
                "Try a ticker or company name, for example NVDA, Tesla, or bitcoin."
            )

        trace = [
            TraceStep(
                step_id="orchestrator.plan",
                agent="global_orchestrator",
                action="Route an investor-specific request to the suitability challenge",
                delegated_to=["request_parser", self.name],
                details={"persona": persona["name"]},
            ),
            TraceStep(
                step_id="parser.extract",
                parent_id="orchestrator.plan",
                agent="request_parser",
                action=(
                    f"Deterministically extracted {request['ticker']} ({request['name']}) at "
                    f"{request['weight']:.1%} ({'stated' if request['weight_source'] != 'assumed' else 'assumed, none stated'})"
                ),
                details={"source": UNIVERSE_SOURCE, **request},
            ),
        ]

        scenarios = self.build_scenarios(persona_id, request)
        trace.append(TraceStep(
            step_id="challenge.build",
            parent_id="orchestrator.plan",
            agent=self.name,
            action="Build the requested allocation plus profile-safe alternatives: "
            + ", ".join(item["label"] for item in scenarios),
            delegated_to=["aws_financial_tools"],
        ))

        all_allocations = {name: 0.0 for item in scenarios for name in item["strategy_allocations"]}
        calculation = self.financial_tool(
            "compare_scenarios",
            {
                "analysis_id": analysis_id,
                "scenarios": [
                    {"id": item["id"], "label": item["label"], "strategy_allocations": item["strategy_allocations"]}
                    for item in scenarios
                ],
                "strategy_holdings": holdings_for(all_allocations),
                "start_date": "2023-11-13",
                "end_date": "2026-11-12",
                "portfolio_value": portfolio_value,
                "focus_ticker": request["ticker"],
            },
        )
        by_id = {item["id"]: item for item in calculation["scenarios"]}
        evidence_ids = [e["evidence_id"] for item in calculation["scenarios"] for e in item["evidence"]]
        trace.append(TraceStep(
            step_id="tool.financial_lambda",
            parent_id="challenge.build",
            agent="aws_financial_tools",
            action="Measure every scenario on one calendar, replay 2022, and time the recovery in AWS Lambda",
            evidence_ids=evidence_ids,
            details={"aws_request_id": calculation.get("aws_request_id", "unknown"), "operation": "compare_scenarios"},
        ))

        results: List[ScenarioResult] = []
        for item in scenarios:
            measured = by_id[item["id"]]
            values = {e["evidence_id"].rsplit(".", 1)[1]: e["value"] for e in measured["evidence"]}
            prefix = f"scenario.{item['id']}"
            findings = profile_controls(
                persona_id,
                measured["asset_weights"],
                values.get("stress_2022_drawdown"),
                values.get("months_underwater"),
                {
                    "stress_drawdown": f"{prefix}.stress_2022_drawdown",
                    "months_underwater": f"{prefix}.months_underwater",
                    "largest_position": f"{prefix}.focus_position",
                },
                include_passes=False,
                focus_ticker=request["ticker"],
            )
            results.append(ScenarioResult(
                id=item["id"],
                label=item["label"],
                description=item["description"],
                strategy_allocations=item["strategy_allocations"],
                largest_position_ticker=measured["largest_position_ticker"],
                evidence=measured["evidence"],
                recovery=measured.get("recovery", {}),
                findings=findings,
                within_profile=not any(
                    f.severity in ("warning", "block") and f.rule_id not in CAUTION_ONLY_RULES
                    for f in findings
                ),
            ))

        result_map = {item.id: item for item in results}
        if result_map["requested"].within_profile:
            verdict, recommended = "aligned", "requested"
        elif "capped" in result_map and result_map["capped"].within_profile:
            verdict, recommended = "cap", "capped"
        elif result_map["alternative"].within_profile:
            verdict, recommended = "alternative", "alternative"
        else:
            verdict, recommended = "conflict", "baseline"

        governance = [
            GovernanceFinding(
                rule_id="SIMULATION_ONLY",
                severity="info",
                message="This compares fictional portfolios and cannot execute a trade.",
            )
        ]
        if request["weight_source"] == "assumed":
            governance.append(GovernanceFinding(
                rule_id="POSITION_SIZE_ASSUMED",
                severity="info",
                message=f"No size was stated, so a {DEFAULT_WEIGHT:.0%} position was assumed for illustration.",
            ))
        requested_rules = [
            f.rule_id for f in result_map["requested"].findings if f.rule_id not in CAUTION_ONLY_RULES
        ]
        if requested_rules:
            governance.append(GovernanceFinding(
                rule_id="REQUEST_CONFLICTS_WITH_PROFILE",
                severity="warning",
                message=(
                    f"The request as stated conflicts with {persona['name']}'s profile "
                    f"({', '.join(rule.replace('_', ' ').lower() for rule in requested_rules)}). "
                    "The system will not simply agree; it shows what fits instead."
                ),
                evidence_ids=[i for f in result_map["requested"].findings for i in f.evidence_ids],
            ))
        else:
            governance.append(GovernanceFinding(
                rule_id="REQUEST_WITHIN_PROFILE",
                severity="info",
                message=f"The request as stated stays within {persona['name']}'s fictional risk budget.",
            ))
        trace.append(TraceStep(
            step_id="governance.review",
            parent_id="orchestrator.plan",
            agent="governance_agent",
            action=f"Apply {persona['name']}'s risk budget (loss, recovery, single-company, crypto, ESG) to every scenario",
            evidence_ids=sorted({i for item in results for f in item.findings for i in f.evidence_ids}),
            details={"within_profile": {item.id: item.within_profile for item in results}},
        ))
        trace.append(TraceStep(
            step_id="challenge.verdict",
            parent_id="governance.review",
            agent=self.name,
            action=f"Verdict '{verdict}': recommend the '{result_map[recommended].label}' scenario",
        ))

        registry = {
            **registry_from_scenarios([
                {"label": item.label, "evidence": item.evidence} for item in results
            ]),
            **registry_from_budget(persona_id),
            "request.weight": _entry(
                "request.weight", "request.weight", "Requested position size", request["weight"], "percent",
                "Parsed from the investor's request" if request["weight_source"] != "assumed"
                else "Assumed position size (none stated)", "parser-v1", "request",
            ),
        }
        baseline_values = {e["evidence_id"].rsplit(".", 1)[1]: e["value"] for e in result_map["baseline"].evidence}
        packet = {
            "question": message,
            "investor": {
                "name": persona["name"],
                "risk": persona["risk"],
                "horizon_years": persona["horizon_years"],
                "objective": persona["objective"],
                "preferences": persona["preferences"],
            },
            "request": {"asset": request["name"], "ticker": request["ticker"], "size_token": "request.weight",
                        "size_was_stated": request["weight_source"] != "assumed"},
            "verdict": verdict,
            "recommended_scenario": recommended,
            "recommended_versus_requested": {
                key: direction(
                    next(e["value"] for e in result_map["requested"].evidence if e["evidence_id"].endswith("." + key)),
                    value,
                    key,
                )
                for key, value in (
                    (e["evidence_id"].rsplit(".", 1)[1], e["value"]) for e in result_map[recommended].evidence
                )
                if key in CHALLENGE_METRICS
            },
            "scenarios": [
                {
                    "id": item.id,
                    "label": scrub_digits(item.label),
                    "within_profile": item.within_profile,
                    "governance": [
                        {"rule_id": f.rule_id, "message": scrub_digits(f.message)} for f in item.findings
                    ],
                    "versus_current_portfolio": {
                        key: direction(baseline_values.get(key), value, key)
                        for key, value in (
                            (e["evidence_id"].rsplit(".", 1)[1], e["value"]) for e in item.evidence
                        )
                        if key in CHALLENGE_METRICS
                    },
                }
                for item in results
            ],
            "limitations": calculation["limitations"],
        }
        figures = (
            f"Verified figures: as requested, {request['ticker']} would total "
            "{{scenario.requested.focus_position}} of the portfolio, and in the 2022 replay that portfolio fell "
            "{{scenario.requested.stress_2022_drawdown}} ({{scenario.requested.stress_2022_loss_cad}} on the "
            f"fictional balance) against {persona['name']}'s {{{{budget.max_stress_drawdown}}}} loss budget"
        )
        if recommended != "requested":
            figures += (
                f"; the recommended scenario ({result_map[recommended].label}) fell "
                f"{{{{scenario.{recommended}.stress_2022_drawdown}}}}, with {request['ticker']} totalling "
                f"{{{{scenario.{recommended}.focus_position}}}}"
            )
        figures += "."
        explanation = self.explainability_agent.synthesize_packet(packet, registry, list(registry), figures)
        trace.append(TraceStep(
            step_id="explainability.synthesize",
            parent_id="challenge.verdict",
            agent=self.explainability_agent.name,
            action="Amazon Bedrock writes digit-free prose; code appends verified figures from the Lambda evidence",
            evidence_ids=explanation.evidence_ids,
            details={"model_id": explanation.model_id},
        ))

        return ChallengeResponse(
            analysis_id=analysis_id,
            persona_id=persona_id,
            question=message,
            parsed_request=request,
            verdict=verdict,
            recommended_scenario=recommended,
            scenarios=results,
            answer=explanation.answer,
            answer_segments=explanation.segments,
            evidence=registry,
            governance=governance,
            trace=trace,
            assumptions=[
                *calculation["assumptions"],
                f"{persona['name']}'s fictional balance is ${portfolio_value:,.0f}; risk budgets are a documented demo policy.",
            ],
            limitations=list(dict.fromkeys([*calculation["limitations"], *explanation.limitations])),
            data_sources=[*calculation["data_sources"], UNIVERSE_SOURCE],
            windows=calculation.get("windows", {}),
            model_id=explanation.model_id,
        )
