from __future__ import annotations

import math
import statistics
from datetime import date
from typing import Dict, Iterable, List, Mapping, Sequence

try:
    from .data_access import MarketDataset
except ImportError:  # Lambda CodeUri places modules at the runtime root.
    from data_access import MarketDataset


FORMULA_VERSION = "portfolio-risk-v1"
INVESTMENT_FORMULA_VERSION = "investment-intelligence-v1"
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


def correlation(left: Sequence[float], right: Sequence[float]) -> float:
    if len(left) != len(right) or len(left) < 2:
        raise ValueError("correlation requires aligned return series")
    if statistics.stdev(left) == 0 or statistics.stdev(right) == 0:
        return 0.0
    return statistics.correlation(left, right)


def variance_risk_contribution(
    asset_returns: Sequence[float],
    portfolio_returns_: Sequence[float],
    asset_weight: float,
) -> float:
    """Direct target contribution as a fraction of portfolio return variance."""
    portfolio_variance = statistics.variance(portfolio_returns_)
    if portfolio_variance == 0 or asset_weight == 0:
        return 0.0
    return asset_weight * statistics.covariance(
        asset_returns, portfolio_returns_
    ) / portfolio_variance


def _metric(
    evidence_id: str,
    label: str,
    current: float,
    proposed: float,
    unit: str,
    source: str,
) -> dict:
    return {
        "evidence_id": evidence_id,
        "label": label,
        "current": current,
        "proposed": proposed,
        "delta": proposed - current,
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

    return {
        "status": "ok",
        "operation": "compare_strategy_shift",
        "analysis_id": event["analysis_id"],
        "current_allocations": allocations,
        "proposed_allocations": proposed_allocations,
        "metrics": metrics,
        "conclusion": conclusion,
        "performance_series": _performance_series(
            dates, current_returns, proposed_returns
        ),
        "assumptions": [
            "Adjusted close is used for historical returns.",
            "USD listings are converted to CAD with the latest USD/CAD observation on or before each price date.",
            "Only dates shared by every holding are used.",
            "Portfolio weights are held constant through daily rebalancing.",
            f"The analysis window is {dates[0].isoformat()} through {dates[-1].isoformat()} ({len(dates)} common observations).",
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


def _latest_cad_price(
    dataset: MarketDataset, ticker: str, end_date: date
) -> tuple[float, str, float]:
    observations = [
        item for item in dataset.prices.get(ticker, []) if item.observation_date <= end_date
    ]
    if not observations:
        raise ValueError(f"no market price for {ticker} on or before {end_date}")
    observation = observations[-1]
    fx = 1.0 if observation.currency == "CAD" else dataset.prior_usdcad(observation.observation_date)
    return observation.close_price * fx, observation.observation_date.isoformat(), fx


def _etf_weights(event: dict, target_ticker: str) -> dict[str, dict]:
    result = {}
    for item in event.get("etf_constituents", {}).get("holdings", []):
        if item.get("constituent_ticker") == target_ticker:
            result[item["etf_ticker"]] = item
    return result


def _account_values(
    account: dict, dataset: MarketDataset, end_date: date
) -> tuple[dict[str, float], dict[str, dict]]:
    values: dict[str, float] = {}
    metadata: dict[str, dict] = {}
    for holding in account["holdings"]:
        ticker = holding["ticker"]
        price_cad, as_of, fx = _latest_cad_price(dataset, ticker, end_date)
        values[ticker] = values.get(ticker, 0.0) + float(holding["quantity"]) * price_cad
        metadata[ticker] = {"price_cad": price_cad, "as_of": as_of, "fx": fx}
    return values, metadata


def _exposure(
    account: dict,
    values: Mapping[str, float],
    target_ticker: str,
    etf_weights: Mapping[str, dict],
) -> dict:
    total = sum(values.values()) + float(account["cash_cad"])
    if total <= 0:
        raise ValueError(f"account {account['id']} has no value")
    direct_value = values.get(target_ticker, 0.0)
    indirect_breakdown = []
    indirect_value = 0.0
    for ticker, market_value in values.items():
        constituent = etf_weights.get(ticker)
        if not constituent:
            continue
        value = market_value * float(constituent["weight"])
        indirect_value += value
        indirect_breakdown.append(
            {
                "etf_ticker": ticker,
                "etf_market_value_cad": market_value,
                "constituent_weight": float(constituent["weight"]),
                "indirect_value_cad": value,
                "as_of": constituent["as_of"],
                "source": constituent["url"],
            }
        )
    return {
        "account_id": account["id"],
        "account_type": account["type"],
        "total_value_cad": total,
        "direct_value_cad": direct_value,
        "indirect_value_cad": indirect_value,
        "total_exposure_cad": direct_value + indirect_value,
        "direct_weight": direct_value / total,
        "indirect_weight": indirect_value / total,
        "total_weight": (direct_value + indirect_value) / total,
        "indirect_breakdown": indirect_breakdown,
    }


def analyze_holdings_exposure(event: dict, dataset: MarketDataset) -> dict:
    target = event["target_ticker"]
    end_date = date.fromisoformat(event["end_date"])
    etf_weights = _etf_weights(event, target)
    accounts = []
    total_value = 0.0
    direct = 0.0
    indirect = 0.0
    for account in event["accounts"]:
        values, metadata = _account_values(account, dataset, end_date)
        exposure = _exposure(account, values, target, etf_weights)
        exposure["price_metadata"] = metadata
        accounts.append(exposure)
        total_value += exposure["total_value_cad"]
        direct += exposure["direct_value_cad"]
        indirect += exposure["indirect_value_cad"]
    source = "; ".join(dataset.sources)
    evidence = [
        {
            "evidence_id": "holdings.portfolio.direct_exposure",
            "category": "holdings",
            "label": f"Direct {target} exposure across accounts",
            "value": direct / total_value,
            "unit": "ratio",
            "source": source,
            "as_of": end_date.isoformat(),
            "details": {"value_cad": direct},
        },
        {
            "evidence_id": "holdings.portfolio.indirect_exposure",
            "category": "holdings",
            "label": f"Indirect {target} exposure through covered ETFs",
            "value": indirect / total_value,
            "unit": "ratio",
            "source": event["etf_constituents"]["fixture_version"],
            "as_of": event["etf_constituents"]["retrieved_at"],
            "details": {"value_cad": indirect, "offline_fixture": True},
        },
    ]
    return {
        "status": "ok",
        "operation": "analyze_holdings_exposure",
        "analysis_id": event["analysis_id"],
        "target_ticker": target,
        "accounts": accounts,
        "portfolio": {
            "total_value_cad": total_value,
            "direct_value_cad": direct,
            "indirect_value_cad": indirect,
            "total_exposure_cad": direct + indirect,
            "direct_weight": direct / total_value,
            "indirect_weight": indirect / total_value,
            "total_weight": (direct + indirect) / total_value,
        },
        "evidence": evidence,
        "limitations": [
            "ETF look-through uses a reviewed offline issuer fixture and may differ from current holdings.",
            "Only ETF-to-target mappings present in the fixture are included in indirect exposure.",
        ],
    }


def market_snapshot(event: dict, dataset: MarketDataset) -> dict:
    ticker = event["target_ticker"]
    start_date = date.fromisoformat(event["start_date"])
    end_date = date.fromisoformat(event["end_date"])
    price_cad, as_of, fx = _latest_cad_price(dataset, ticker, end_date)
    series = cad_price_series(dataset, [ticker], start_date, end_date)[ticker]
    dates = sorted(series)
    values = [series[item] for item in dates]
    returns = [values[index] / values[index - 1] - 1.0 for index in range(1, len(values))]

    def trailing(period: int) -> float | None:
        if len(values) <= period:
            return None
        return values[-1] / values[-period - 1] - 1.0

    source = "; ".join(dataset.sources)
    metrics = {
        "price_cad": price_cad,
        "price_as_of": as_of,
        "usdcad": fx,
        "return_1m": trailing(21),
        "return_3m": trailing(63),
        "return_12m": trailing(252),
        "annualized_volatility": annualized_volatility(returns),
        "maximum_drawdown": maximum_drawdown(returns),
    }
    evidence = [
        {
            "evidence_id": f"market.{ticker}.price_cad",
            "category": "market",
            "label": f"Latest available {ticker} close converted to CAD",
            "value": price_cad,
            "unit": "CAD per share",
            "source": source,
            "as_of": as_of,
            "details": {"usdcad": fx, "not_real_time": True},
        },
        {
            "evidence_id": f"market.{ticker}.historical_volatility",
            "category": "market",
            "label": f"Historical annualized volatility for {ticker}",
            "value": metrics["annualized_volatility"],
            "unit": "ratio",
            "source": source,
            "as_of": as_of,
            "details": {"formula_version": INVESTMENT_FORMULA_VERSION},
        },
    ]
    return {
        "status": "ok",
        "operation": "market_snapshot",
        "analysis_id": event["analysis_id"],
        "target_ticker": ticker,
        "metrics": metrics,
        "evidence": evidence,
        "limitations": ["The latest available dataset close is historical and is not a real-time quote."],
    }


def simulate_account_purchase(event: dict, dataset: MarketDataset) -> dict:
    target = event["target_ticker"]
    account_id = event["account_id"]
    accounts = event["accounts"]
    account = next((item for item in accounts if item["id"] == account_id), None)
    if not account:
        raise ValueError(f"unknown account: {account_id}")
    start_date = date.fromisoformat(event["start_date"])
    end_date = date.fromisoformat(event["end_date"])
    price_cad, price_as_of, fx = _latest_cad_price(dataset, target, end_date)
    amount = float(event["amount"])
    amount_cad = amount if event["currency"] == "CAD" else amount * fx
    values, _ = _account_values(account, dataset, end_date)
    current_total = sum(values.values()) + float(account["cash_cad"])
    cash_remaining = float(account["cash_cad"]) - amount_cad
    shares = amount_cad / price_cad
    blocked = cash_remaining < 0
    proposed_values = dict(values)
    if not blocked:
        proposed_values[target] = proposed_values.get(target, 0.0) + amount_cad

    tickers = sorted(set(values) | {target})
    series = cad_price_series(dataset, tickers, start_date, end_date)
    dates = common_dates(series)
    current_weights = {ticker: value / current_total for ticker, value in values.items()}
    proposed_weights = {
        ticker: value / current_total for ticker, value in proposed_values.items()
    }
    current_returns = portfolio_returns(series, dates, current_weights)
    proposed_returns = portfolio_returns(series, dates, proposed_weights)
    target_returns = [
        series[target][dates[index]] / series[target][dates[index - 1]] - 1.0
        for index in range(1, len(dates))
    ]
    current_target_weight = current_weights.get(target, 0.0)
    proposed_target_weight = proposed_weights.get(target, 0.0)
    current_concentration_weights = {**current_weights, "CASH": float(account["cash_cad"]) / current_total}
    proposed_concentration_weights = (
        current_concentration_weights
        if blocked
        else {**proposed_weights, "CASH": cash_remaining / current_total}
    )
    etf_weights = _etf_weights(event, target)
    current_exposure = _exposure(account, values, target, etf_weights)
    proposed_account = (
        account if blocked else {**account, "cash_cad": cash_remaining}
    )
    proposed_exposure = _exposure(proposed_account, proposed_values, target, etf_weights)

    portfolio_total = 0.0
    portfolio_target = 0.0
    for candidate in accounts:
        candidate_values, _ = _account_values(candidate, dataset, end_date)
        exposure = _exposure(candidate, candidate_values, target, etf_weights)
        portfolio_total += exposure["total_value_cad"]
        portfolio_target += exposure["total_exposure_cad"]
    portfolio_current_weight = portfolio_target / portfolio_total
    portfolio_proposed_weight = (
        portfolio_current_weight if blocked else (portfolio_target + amount_cad) / portfolio_total
    )

    constraints = account["risk_constraints"]
    proposed_weight = proposed_exposure["total_weight"]
    if blocked:
        compatibility = "blocked"
    elif cash_remaining < float(constraints["minimum_cash_cad"]):
        compatibility = "conflict"
    elif proposed_weight > float(constraints["max_single_company_exposure"]):
        compatibility = "conflict"
    elif account["risk_tolerance"] == "conservative":
        compatibility = "caution"
    else:
        compatibility = "compatible"

    source = "; ".join(dataset.sources)
    prefix = f"simulation.{account_id}"
    option = {
        "account_id": account_id,
        "account_type": account["type"],
        "account_name": account["name"],
        "objective": account["objective"],
        "risk_tolerance": account["risk_tolerance"],
        "compatibility": compatibility,
        "shares_purchasable": 0.0 if blocked else shares,
        "purchase_price_cad": price_cad,
        "remaining_cash_cad": cash_remaining,
        "current_nvda_exposure": current_exposure["total_weight"],
        "proposed_nvda_exposure": current_exposure["total_weight"] if blocked else proposed_weight,
        "portfolio_current_nvda_exposure": portfolio_current_weight,
        "portfolio_proposed_nvda_exposure": portfolio_proposed_weight,
        "current_volatility": annualized_volatility(current_returns),
        "proposed_volatility": annualized_volatility(proposed_returns),
        "current_max_drawdown": maximum_drawdown(current_returns),
        "proposed_max_drawdown": maximum_drawdown(proposed_returns),
        "current_concentration": concentration(current_concentration_weights),
        "proposed_concentration": concentration(proposed_concentration_weights),
        "current_target_correlation": correlation(target_returns, current_returns),
        "proposed_target_correlation": correlation(target_returns, proposed_returns),
        "current_target_risk_contribution": variance_risk_contribution(
            target_returns, current_returns, current_target_weight
        ),
        "proposed_target_risk_contribution": variance_risk_contribution(
            target_returns, proposed_returns, proposed_target_weight
        ),
        "evidence_ids": [
            f"{prefix}.nvda_exposure",
            f"{prefix}.volatility",
            f"{prefix}.maximum_drawdown",
            f"{prefix}.concentration",
            f"{prefix}.correlation",
            f"{prefix}.risk_contribution",
            f"{prefix}.cash",
        ],
    }
    evidence = [
        {
            "evidence_id": f"{prefix}.nvda_exposure",
            "category": "calculation",
            "label": f"{account['type']} direct and covered indirect {target} exposure",
            "value": option["proposed_nvda_exposure"],
            "unit": "ratio",
            "source": source,
            "as_of": price_as_of,
            "details": {"current": option["current_nvda_exposure"], "blocked": blocked},
        },
        {
            "evidence_id": f"{prefix}.volatility",
            "category": "calculation",
            "label": f"{account['type']} historical annualized volatility after simulation",
            "value": option["proposed_volatility"],
            "unit": "ratio",
            "source": source,
            "as_of": price_as_of,
            "details": {"current": option["current_volatility"]},
        },
        {
            "evidence_id": f"{prefix}.maximum_drawdown",
            "category": "calculation",
            "label": f"{account['type']} historical maximum drawdown after simulation",
            "value": option["proposed_max_drawdown"],
            "unit": "ratio",
            "source": source,
            "as_of": price_as_of,
            "details": {"current": option["current_max_drawdown"]},
        },
        {
            "evidence_id": f"{prefix}.concentration",
            "category": "calculation",
            "label": f"{account['type']} concentration after simulation",
            "value": option["proposed_concentration"],
            "unit": "HHI",
            "source": "fictional holdings plus historical market values",
            "as_of": price_as_of,
            "details": {"current": option["current_concentration"]},
        },
        {
            "evidence_id": f"{prefix}.correlation",
            "category": "calculation",
            "label": f"{target} historical correlation with the {account['type']} portfolio",
            "value": option["proposed_target_correlation"],
            "unit": "correlation",
            "source": source,
            "as_of": price_as_of,
            "details": {"current": option["current_target_correlation"]},
        },
        {
            "evidence_id": f"{prefix}.risk_contribution",
            "category": "calculation",
            "label": f"Direct {target} contribution to {account['type']} return variance",
            "value": option["proposed_target_risk_contribution"],
            "unit": "variance share",
            "source": source,
            "as_of": price_as_of,
            "details": {
                "current": option["current_target_risk_contribution"],
                "scope": "direct target position only",
            },
        },
        {
            "evidence_id": f"{prefix}.cash",
            "category": "governance",
            "label": f"{account['type']} cash remaining after simulation",
            "value": cash_remaining,
            "unit": "CAD",
            "source": "fictional-investor-v1",
            "as_of": price_as_of,
            "details": {"minimum_cash_cad": constraints["minimum_cash_cad"]},
        },
    ]
    return {
        "status": "ok",
        "operation": "simulate_account_purchase",
        "analysis_id": event["analysis_id"],
        "option": option,
        "evidence": evidence,
        "assumptions": [
            "Fractional shares are allowed for comparison purposes.",
            "The purchase uses the latest available historical close converted to CAD.",
            "Cash has a zero return in the historical risk comparison.",
            "Weights are based on market values at the analysis end date and held constant for historical comparison.",
            "Risk contribution is the direct target weight times its covariance with the portfolio, divided by portfolio return variance.",
        ],
        "limitations": [
            "No order, commission, spread, tax, contribution-room, or settlement effect is modeled.",
            "Historical risk metrics do not predict future outcomes.",
            "Target risk contribution covers the direct position; ETF look-through is reported separately and is not decomposed from ETF return history.",
        ],
    }
