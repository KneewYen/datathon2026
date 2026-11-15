from __future__ import annotations

import math
import statistics
from datetime import date
from typing import Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

try:
    from .data_access import MarketDataset
except ImportError:  # Lambda CodeUri places modules at the runtime root.
    from data_access import MarketDataset


FORMULA_VERSION = "portfolio-risk-v1"
TRADING_DAYS_PER_YEAR = 252


def apply_shift(
    allocations: Mapping[str, float],
    from_strategy: str,
    to_strategy: str,
    amount: float,
) -> Dict[str, float]:
    proposed = dict(allocations)
    if from_strategy not in proposed or to_strategy not in proposed:
        raise ValueError("shift strategies must exist in strategy_allocations")
    if amount <= 0 or proposed[from_strategy] + 1e-12 < amount:
        raise ValueError("invalid strategy shift amount")
    proposed[from_strategy] = round(proposed[from_strategy] - amount, 12)
    proposed[to_strategy] = round(proposed[to_strategy] + amount, 12)
    if abs(sum(proposed.values()) - 1.0) > 1e-9:
        raise ValueError("proposed strategy allocations do not sum to 1")
    return proposed


def asset_weights(
    strategy_allocations: Mapping[str, float],
    strategy_holdings: Mapping[str, Mapping[str, float]],
) -> Dict[str, float]:
    weights: Dict[str, float] = {}
    for strategy, allocation in strategy_allocations.items():
        holdings = strategy_holdings.get(strategy)
        if holdings is None:
            raise ValueError(f"missing holdings for strategy: {strategy}")
        if abs(sum(holdings.values()) - 1.0) > 1e-9:
            raise ValueError(f"holdings for {strategy} do not sum to 1")
        if allocation <= 0:
            continue
        for ticker, holding_weight in holdings.items():
            weights[ticker] = weights.get(ticker, 0.0) + allocation * holding_weight
    if abs(sum(weights.values()) - 1.0) > 1e-9:
        raise ValueError("asset weights do not sum to 1")
    return weights


def cad_price_series(
    dataset: MarketDataset,
    tickers: Iterable[str],
    start_date: date,
    end_date: date,
) -> Dict[str, Dict[date, float]]:
    result: Dict[str, Dict[date, float]] = {}
    for ticker in tickers:
        if ticker not in dataset.prices:
            raise ValueError(f"unsupported ticker: {ticker}")
        series: Dict[date, float] = {}
        for observation in dataset.prices[ticker]:
            if not (start_date <= observation.observation_date <= end_date):
                continue
            if observation.currency == "CAD":
                value = observation.adjusted_close
            elif observation.currency == "USD":
                value = observation.adjusted_close * dataset.prior_usdcad(
                    observation.observation_date
                )
            else:
                raise ValueError(
                    f"unsupported listing currency {observation.currency} for {ticker}"
                )
            series[observation.observation_date] = value
        if not series:
            raise ValueError(f"no prices for {ticker} in the requested window")
        result[ticker] = series
    return result


def common_dates(series: Mapping[str, Mapping[date, float]]) -> List[date]:
    date_sets = [set(values) for values in series.values()]
    if not date_sets:
        raise ValueError("portfolio has no assets")
    dates = sorted(set.intersection(*date_sets))
    if len(dates) < 60:
        raise ValueError("fewer than 60 common price observations in the requested window")
    return dates


def portfolio_returns(
    series: Mapping[str, Mapping[date, float]],
    dates: Sequence[date],
    weights: Mapping[str, float],
) -> List[float]:
    returns: List[float] = []
    for position in range(1, len(dates)):
        previous_date = dates[position - 1]
        current_date = dates[position]
        portfolio_return = 0.0
        for ticker, weight in weights.items():
            previous = series[ticker][previous_date]
            current = series[ticker][current_date]
            portfolio_return += weight * (current / previous - 1.0)
        returns.append(portfolio_return)
    return returns


def annualized_volatility(returns: Sequence[float]) -> float:
    if len(returns) < 2:
        raise ValueError("at least two returns are required")
    return statistics.stdev(returns) * math.sqrt(TRADING_DAYS_PER_YEAR)


def annualized_return(returns: Sequence[float]) -> float:
    growth = math.prod(1.0 + value for value in returns)
    return growth ** (TRADING_DAYS_PER_YEAR / len(returns)) - 1.0


def total_return(returns: Sequence[float]) -> float:
    return math.prod(1.0 + value for value in returns) - 1.0


def maximum_drawdown(returns: Sequence[float]) -> float:
    wealth = 1.0
    peak = 1.0
    worst = 0.0
    for value in returns:
        wealth *= 1.0 + value
        peak = max(peak, wealth)
        worst = min(worst, wealth / peak - 1.0)
    return worst


def concentration(weights: Mapping[str, float]) -> float:
    return sum(weight * weight for weight in weights.values())


STRESS_WINDOW = {
    "id": "stress_2022",
    "label": "2022 stock-and-bond selloff",
    "start": "2022-01-01",
    "end": "2022-12-31",
}
FULL_HISTORY_WINDOW = {
    "id": "full_history",
    "label": "Full starter history (includes 2022)",
    "start": "2021-11-12",
    "end": "2026-11-12",
}
DAYS_PER_MONTH = 365.25 / 12


def _window(spec: Mapping | None, default: Mapping) -> dict:
    merged = {**default, **(spec or {})}
    start = date.fromisoformat(str(merged["start"]))
    end = date.fromisoformat(str(merged["end"]))
    if start >= end:
        raise ValueError(f"window {merged['id']} must start before it ends")
    return {"id": str(merged["id"]), "label": str(merged["label"]), "start": start, "end": end}


def window_returns(
    series: Mapping[str, Mapping[date, float]],
    weights: Mapping[str, float],
    start: date,
    end: date,
) -> Tuple[List[date], List[float]]:
    """Daily returns over the dates shared by every ticker in ``series`` inside the window."""
    window = {
        ticker: {day: value for day, value in values.items() if start <= day <= end}
        for ticker, values in series.items()
    }
    dates = common_dates(window)
    return dates, portfolio_returns(window, dates, weights)


def drawdown_recovery(
    dates: Sequence[date],
    returns: Sequence[float],
    trough_from: date,
    trough_by: date,
) -> dict:
    """Worst peak-to-trough fall with its trough inside [trough_from, trough_by], then time to regain the peak."""
    wealth = 1.0
    peak_value, peak_date = 1.0, dates[0]
    worst, worst_peak_value, worst_peak_date, trough_date = 0.0, 1.0, dates[0], None
    path = []
    for day, value in zip(dates[1:], returns):
        wealth *= 1.0 + value
        path.append((day, wealth))
        if wealth > peak_value:
            peak_value, peak_date = wealth, day
        if trough_from <= day <= trough_by:
            drawdown = wealth / peak_value - 1.0
            if drawdown < worst:
                worst, worst_peak_value, worst_peak_date, trough_date = (
                    drawdown,
                    peak_value,
                    peak_date,
                    day,
                )
    if trough_date is None:
        return {"peak_to_trough": 0.0, "peak_date": None, "trough_date": None, "recovery_date": None, "months_underwater": 0.0}
    for day, value in path:
        if day > trough_date and value >= worst_peak_value:
            return {
                "peak_to_trough": worst,
                "peak_date": worst_peak_date.isoformat(),
                "trough_date": trough_date.isoformat(),
                "recovery_date": day.isoformat(),
                "months_underwater": (day - worst_peak_date).days / DAYS_PER_MONTH,
            }
    return {
        "peak_to_trough": worst,
        "peak_date": worst_peak_date.isoformat(),
        "trough_date": trough_date.isoformat(),
        "recovery_date": None,
        "months_underwater": None,
    }


def _conclusion(current_returns: Sequence[float], proposed_returns: Sequence[float]) -> str:
    volatility_reduced = annualized_volatility(proposed_returns) < annualized_volatility(current_returns)
    drawdown_improved = maximum_drawdown(proposed_returns) > maximum_drawdown(current_returns)
    if volatility_reduced and drawdown_improved:
        return "risk_reduced"
    if not volatility_reduced and not drawdown_improved:
        return "risk_increased"
    return "mixed"


def _metric(
    evidence_id: str,
    label: str,
    current: Optional[float],
    proposed: Optional[float],
    unit: str,
    source: str,
) -> dict:
    return {
        "evidence_id": evidence_id,
        "label": label,
        "current": current,
        "proposed": proposed,
        "delta": None if current is None or proposed is None else proposed - current,
        "unit": unit,
        "source": source,
        "formula_version": FORMULA_VERSION,
    }
def _performance_series(
    dates: Sequence[date],
    current_returns: Sequence[float],
    proposed_returns: Sequence[float],
    max_points: int = 96,
) -> List[dict]:
    current_value = 1.0
    proposed_value = 1.0
    all_points = []
    for observation_date, current_return, proposed_return in zip(
        dates[1:], current_returns, proposed_returns
    ):
        current_value *= 1.0 + current_return
        proposed_value *= 1.0 + proposed_return
        all_points.append(
            {
                "date": observation_date.isoformat(),
                "current": current_value - 1.0,
                "proposed": proposed_value - 1.0,
            }
        )
    step = max(1, math.ceil(len(all_points) / max_points))
    sampled = all_points[::step]
    if sampled and sampled[-1] != all_points[-1]:
        sampled.append(all_points[-1])
    return sampled


def compare_strategy_shift(event: dict, dataset: MarketDataset) -> dict:
    allocations = {key: float(value) for key, value in event["strategy_allocations"].items()}
    shift = event["shift"]
    strategy_holdings = event["strategy_holdings"]
    start_date = date.fromisoformat(event["start_date"])
    end_date = date.fromisoformat(event["end_date"])

    if abs(sum(allocations.values()) - 1.0) > 1e-9:
        raise ValueError("strategy allocations must sum to 1")
    proposed_allocations = apply_shift(
        allocations,
        shift["from_strategy"],
        shift["to_strategy"],
        float(shift["amount"]),
    )
    current_weights = asset_weights(allocations, strategy_holdings)
    proposed_weights = asset_weights(proposed_allocations, strategy_holdings)
    tickers = sorted(set(current_weights) | set(proposed_weights))
    series = cad_price_series(dataset, tickers, start_date, end_date)
    dates = common_dates(series)
    current_returns = portfolio_returns(series, dates, current_weights)
    proposed_returns = portfolio_returns(series, dates, proposed_weights)

    source = "; ".join(dataset.sources) or "provided market dataset"
    metrics = [
        _metric(
            "metric.annualized_volatility",
            "Annualized volatility",
            annualized_volatility(current_returns),
            annualized_volatility(proposed_returns),
            "percent",
            source,
        ),
        _metric(
            "metric.maximum_drawdown",
            "Maximum drawdown",
            maximum_drawdown(current_returns),
            maximum_drawdown(proposed_returns),
            "percent",
            source,
        ),
        _metric(
            "metric.annualized_return",
            "Annualized historical return",
            annualized_return(current_returns),
            annualized_return(proposed_returns),
            "percent",
            source,
        ),
        _metric(
            "metric.total_return",
            "Total historical return",
            total_return(current_returns),
            total_return(proposed_returns),
            "percent",
            source,
        ),
        _metric(
            "metric.concentration_hhi",
            "Asset concentration (HHI)",
            concentration(current_weights),
            concentration(proposed_weights),
            "ratio",
            "strategy basket definitions",
        ),
    ]

    metric_map = {item["evidence_id"]: item for item in metrics}
    volatility_reduced = metric_map["metric.annualized_volatility"]["delta"] < 0
    drawdown_improved = metric_map["metric.maximum_drawdown"]["delta"] > 0
    if volatility_reduced and drawdown_improved:
        conclusion = "risk_reduced"
    elif not volatility_reduced and not drawdown_improved:
        conclusion = "risk_increased"
    else:
        conclusion = "mixed"

    stress = _window(event.get("stress_window"), STRESS_WINDOW)
    full = _window(event.get("full_window"), FULL_HISTORY_WINDOW)
    full_series = cad_price_series(dataset, tickers, full["start"], full["end"])
    stress_profiles = {}
    full_returns = {}
    for name, weights in (("current", current_weights), ("proposed", proposed_weights)):
        _, stress_returns = window_returns(full_series, weights, stress["start"], stress["end"])
        full_dates, full_returns[name] = window_returns(full_series, weights, full["start"], full["end"])
        recovery = drawdown_recovery(full_dates, full_returns[name], stress["start"], stress["end"])
        stress_profiles[name] = {
            "maximum_drawdown": maximum_drawdown(stress_returns),
            "total_return": total_return(stress_returns),
            **recovery,
        }
    metrics.extend(
        [
            _metric(
                "metric.stress_2022_drawdown",
                f"{stress['label']}: maximum drawdown",
                stress_profiles["current"]["maximum_drawdown"],
                stress_profiles["proposed"]["maximum_drawdown"],
                "percent",
                source,
            ),
            _metric(
                "metric.stress_2022_return",
                f"{stress['label']}: total return",
                stress_profiles["current"]["total_return"],
                stress_profiles["proposed"]["total_return"],
                "percent",
                source,
            ),
            _metric(
                "metric.months_underwater",
                "Months from pre-2022 peak to full recovery",
                stress_profiles["current"]["months_underwater"],
                stress_profiles["proposed"]["months_underwater"],
                "months",
                source,
            ),
        ]
    )
    portfolio_value = event.get("portfolio_value")
    if portfolio_value:
        metrics.append(
            _metric(
                "metric.stress_2022_loss_cad",
                "2022-style loss on the fictional balance",
                float(portfolio_value) * stress_profiles["current"]["maximum_drawdown"],
                float(portfolio_value) * stress_profiles["proposed"]["maximum_drawdown"],
                "cad",
                source,
            )
        )
    metrics.extend(
        [
            _metric(
                "metric.full_history_volatility",
                "Full history: annualized volatility",
                annualized_volatility(full_returns["current"]),
                annualized_volatility(full_returns["proposed"]),
                "percent",
                source,
            ),
            _metric(
                "metric.full_history_drawdown",
                "Full history: maximum drawdown",
                maximum_drawdown(full_returns["current"]),
                maximum_drawdown(full_returns["proposed"]),
                "percent",
                source,
            ),
        ]
    )
    robustness_windows = [
        {
            "id": "primary",
            "label": "Requested window",
            "start": dates[0].isoformat(),
            "end": dates[-1].isoformat(),
            "observations": len(dates),
            "conclusion": conclusion,
        },
        {
            "id": full["id"],
            "label": full["label"],
            "start": full_dates[0].isoformat(),
            "end": full_dates[-1].isoformat(),
            "observations": len(full_dates),
            "conclusion": _conclusion(full_returns["current"], full_returns["proposed"]),
        },
    ]

    return {
        "status": "ok",
        "operation": "compare_strategy_shift",
        "analysis_id": event["analysis_id"],
        "current_allocations": allocations,
        "proposed_allocations": proposed_allocations,
        "metrics": metrics,
        "conclusion": conclusion,
        "robustness": {
            "windows": robustness_windows,
            "consistent": len({item["conclusion"] for item in robustness_windows}) == 1,
        },
        "stress_test": {
            "window": {
                "id": stress["id"],
                "label": stress["label"],
                "start": stress["start"].isoformat(),
                "end": stress["end"].isoformat(),
            },
            "current": stress_profiles["current"],
            "proposed": stress_profiles["proposed"],
        },
        "performance_series": _performance_series(
            dates, current_returns, proposed_returns
        ),
        "assumptions": [
            "Adjusted close is used for historical returns.",
            "USD listings are converted to CAD with the latest USD/CAD observation on or before each price date.",
            "Only dates shared by every holding are used.",
            "Portfolio weights are held constant through daily rebalancing.",
            f"The analysis window is {dates[0].isoformat()} through {dates[-1].isoformat()} ({len(dates)} common observations).",
            f"The stress replay uses {stress['label']} ({stress['start'].isoformat()} to {stress['end'].isoformat()}); recovery is measured on the full history through {full_dates[-1].isoformat()}.",
        ],
        "limitations": [
            "Historical performance does not predict future results.",
            "The starter universe has survivorship and selection bias.",
            "Fees, taxes, contribution room, trading costs, and personal tax circumstances are excluded.",
            "Strategy baskets are fictional demonstration assumptions, not recommendations.",
        ],
        "data_sources": dataset.sources,
        "calculation_metadata": {
            "formula_version": FORMULA_VERSION,
            "base_currency": "CAD",
            "calendar_policy": "intersection",
            "rebalance_policy": "constant_weight_daily",
        },
    }


SCENARIO_METRICS = {
    "annualized_volatility": ("Annualized volatility", "percent"),
    "maximum_drawdown": ("Maximum drawdown", "percent"),
    "annualized_return": ("Annualized historical return", "percent"),
    "concentration_hhi": ("Asset concentration (HHI)", "ratio"),
    "largest_position": ("Largest single position", "percent"),
    "focus_position": ("Weight of the requested asset", "percent"),
    "stress_2022_drawdown": ("2022 selloff: maximum drawdown", "percent"),
    "stress_2022_return": ("2022 selloff: total return", "percent"),
    "months_underwater": ("Months from pre-2022 peak to full recovery", "months"),
    "stress_2022_loss_cad": ("2022-style loss on the fictional balance", "cad"),
}


def compare_scenarios(event: dict, dataset: MarketDataset) -> dict:
    """Profile several fictional allocations over the same calendar, stress window, and history."""
    scenarios = event["scenarios"]
    if not 2 <= len(scenarios) <= 6:
        raise ValueError("compare_scenarios needs between 2 and 6 scenarios")
    ids = [str(item["id"]) for item in scenarios]
    if len(ids) != len(set(ids)):
        raise ValueError("scenario IDs must be unique")
    holdings = event["strategy_holdings"]
    weights_by_id = {}
    for item in scenarios:
        allocations = {key: float(value) for key, value in item["strategy_allocations"].items()}
        if abs(sum(allocations.values()) - 1.0) > 1e-9:
            raise ValueError(f"scenario {item['id']} allocations must sum to 1")
        weights_by_id[str(item["id"])] = asset_weights(allocations, holdings)

    primary_start = date.fromisoformat(event["start_date"])
    primary_end = date.fromisoformat(event["end_date"])
    stress = _window(event.get("stress_window"), STRESS_WINDOW)
    full = _window(event.get("full_window"), FULL_HISTORY_WINDOW)
    tickers = sorted({ticker for weights in weights_by_id.values() for ticker in weights})
    series = cad_price_series(
        dataset,
        tickers,
        min(primary_start, full["start"]),
        max(primary_end, full["end"]),
    )
    portfolio_value = event.get("portfolio_value")
    source = "; ".join(dataset.sources) or "provided market dataset"

    results = []
    primary_dates: List[date] = []
    for item in scenarios:
        scenario_id = str(item["id"])
        weights = weights_by_id[scenario_id]
        primary_dates, primary = window_returns(series, weights, primary_start, primary_end)
        _, stressed = window_returns(series, weights, stress["start"], stress["end"])
        full_dates, full_returns = window_returns(series, weights, full["start"], full["end"])
        recovery = drawdown_recovery(full_dates, full_returns, stress["start"], stress["end"])
        largest_ticker = max(weights, key=weights.get)
        values = {
            "annualized_volatility": annualized_volatility(primary),
            "maximum_drawdown": maximum_drawdown(primary),
            "annualized_return": annualized_return(primary),
            "concentration_hhi": concentration(weights),
            "largest_position": weights[largest_ticker],
            "stress_2022_drawdown": maximum_drawdown(stressed),
            "stress_2022_return": total_return(stressed),
            "months_underwater": recovery["months_underwater"],
        }
        if portfolio_value:
            values["stress_2022_loss_cad"] = float(portfolio_value) * values["stress_2022_drawdown"]
        if event.get("focus_ticker"):
            values["focus_position"] = weights.get(str(event["focus_ticker"]), 0.0)
        results.append(
            {
                "id": scenario_id,
                "label": str(item.get("label", scenario_id)),
                "strategy_allocations": item["strategy_allocations"],
                "asset_weights": weights,
                "largest_position_ticker": largest_ticker,
                "recovery": recovery,
                "evidence": [
                    {
                        "evidence_id": f"scenario.{scenario_id}.{key}",
                        "label": SCENARIO_METRICS[key][0],
                        "value": value,
                        "unit": SCENARIO_METRICS[key][1],
                        "source": "strategy basket definitions"
                        if key in ("concentration_hhi", "largest_position", "focus_position")
                        else source,
                        "formula_version": FORMULA_VERSION,
                    }
                    for key, value in values.items()
                ],
            }
        )

    return {
        "status": "ok",
        "operation": "compare_scenarios",
        "analysis_id": event["analysis_id"],
        "scenarios": results,
        "windows": {
            "primary": {"start": primary_dates[0].isoformat(), "end": primary_dates[-1].isoformat(), "observations": len(primary_dates)},
            "stress": {"id": stress["id"], "label": stress["label"], "start": stress["start"].isoformat(), "end": stress["end"].isoformat()},
            "full": {"id": full["id"], "label": full["label"], "start": full["start"].isoformat(), "end": full["end"].isoformat()},
        },
        "assumptions": [
            "Adjusted close is used for historical returns.",
            "USD listings are converted to CAD with the latest USD/CAD observation on or before each price date.",
            "Every scenario is measured on the same calendar: dates shared by all holdings across all scenarios.",
            "Portfolio weights are held constant through daily rebalancing.",
            "A requested position is funded proportionally from every existing sleeve.",
            f"The primary window is {primary_dates[0].isoformat()} through {primary_dates[-1].isoformat()} ({len(primary_dates)} common observations).",
            f"The stress replay uses {stress['label']} ({stress['start'].isoformat()} to {stress['end'].isoformat()}).",
        ],
        "limitations": [
            "Historical performance does not predict future results.",
            "A single stock's past behaviour may not repeat; company-specific events dominate concentrated positions.",
            "The starter universe has survivorship and selection bias.",
            "Fees, taxes, contribution room, trading costs, and personal tax circumstances are excluded.",
        ],
        "data_sources": dataset.sources,
        "calculation_metadata": {
            "formula_version": FORMULA_VERSION,
            "base_currency": "CAD",
            "calendar_policy": "intersection",
            "rebalance_policy": "constant_weight_daily",
        },
    }
