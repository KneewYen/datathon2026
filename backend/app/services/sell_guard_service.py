"""Sell-guard service: loads the two simulated datasets and runs the guard.

The calculation lives in ``lambda/financial_tools/sell_guard.py`` so the same
code can run inside AWS Lambda. Until the simulated data is uploaded to S3 and
the Lambda is redeployed (both need explicit approval), the backend runs that
same pure code locally and says so in every response via ``computed_by``.
"""

from __future__ import annotations

import csv
import sys
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List

from app.domain.presets import ACCOUNT_PRESETS, PERSONAS, STRATEGY_HOLDINGS

ROOT = Path(__file__).resolve().parents[3]
SIM = ROOT / "data" / "simulated"
sys.path.insert(0, str(ROOT / "lambda" / "financial_tools"))

import sell_guard  # noqa: E402  (shared with the AWS Lambda package)
import sentiment_tools  # noqa: E402

UNIVERSE = ROOT / "hackathon_info" / "alphaforge_starter" / "assets_universe.csv"


def _rows(path: Path) -> List[Dict[str, str]]:
    with path.open(newline="") as handle:
        return list(csv.DictReader(handle))


def _news(folder: str) -> List[Dict[str, str]]:
    """Model-scored headlines when available, otherwise the raw simulated ones."""
    scored = SIM / folder / "news_scored.csv"
    return _rows(scored if scored.exists() else SIM / folder / "news.csv")


@lru_cache(maxsize=1)
def _data() -> Dict[str, Any]:
    current = _rows(SIM / "current" / "prices.csv")
    change = _rows(SIM / "marketchange" / "prices.csv")
    news = _news("current") + _news("marketchange")
    return {
        "current": current,
        "change": change,
        "news": news,
        "dates": sorted({r["date"] for r in change}),
    }


@lru_cache(maxsize=1)
def _peers() -> Dict[str, List[str]]:
    """Related tickers by sector / asset group, for the cross-ticker sentiment."""
    return sentiment_tools.peer_groups(_rows(UNIVERSE)) if UNIVERSE.exists() else {}


# Server-side market state. "Refreshing" loads the second dataset (market change).
_STATE: Dict[str, Any] = {"refreshed": False}


def market_status() -> Dict[str, Any]:
    data = _data()
    return {
        "refreshed": _STATE["refreshed"],
        "new_price_rows": len(data["change"]) if _STATE["refreshed"] else 0,
        "new_headlines": sum(1 for n in data["news"] if n["date"] in data["dates"]) if _STATE["refreshed"] else 0,
        "computed_by": "local-engine",
    }


def refresh_market() -> Dict[str, Any]:
    _STATE["refreshed"] = True
    return market_status()


def reset_market() -> Dict[str, Any]:
    _STATE["refreshed"] = False
    return market_status()


def _latest() -> str | None:
    return _data()["dates"][-1] if _STATE["refreshed"] else None


def evaluate(action: str, ticker: str) -> Dict[str, Any]:
    as_of = _latest()
    if as_of is None:
        raise LookupError("refresh the live market before checking a trade")
    data = _data()
    result = sell_guard.evaluate_trade(
        action, ticker, data["current"], data["change"], data["news"], as_of, peers=_peers()
    )
    result["computed_by"] = "local-engine"
    return result


def holdings(persona_id: str, allocations: Dict[str, float] | None = None) -> List[Dict[str, Any]]:
    """Each ticker's weight in the persona's default allocation."""
    persona = PERSONAS[persona_id]
    weights: Dict[str, float] = {}
    for strategy, share in (allocations or persona["default_allocations"]).items():
        for ticker, weight in STRATEGY_HOLDINGS.get(strategy, {}).items():
            weights[ticker] = weights.get(ticker, 0.0) + share * weight
    return [{"ticker": t, "weight": w} for t, w in sorted(weights.items(), key=lambda kv: -kv[1])]


def portfolio(persona_id: str, account_type: str | None = None) -> Dict[str, Any]:
    """Fictional positions: shares are sized at the last pre-event close, then repriced."""
    as_of = _latest()
    persona = PERSONAS[persona_id]
    account = ACCOUNT_PRESETS.get(account_type or "")
    balance = float(persona["starting_balance_cad"]) if account is None else float(persona["starting_balance_cad"]) * float(account["share"])
    cash = float(persona["starting_cash_cad"]) if account is None else balance * float(account["cash_share"])
    allocations = None if account is None else account["allocations"]
    data = _data()
    moves = sell_guard.price_volume_signals(data["current"], data["change"], as_of) if as_of else {}
    reference: Dict[str, float] = {}
    latest: Dict[str, float] = {}
    for row in data["current"]:
        reference[row["ticker"]] = float(row["close"])  # rows are date-ordered; the last one wins
    latest.update(reference)
    if as_of:
        for row in data["change"]:
            if row["date"] <= as_of:
                latest[row["ticker"]] = float(row["close"])
    rows = []
    for item in holdings(persona_id, allocations):
        ticker, weight = item["ticker"], item["weight"]
        price = latest[ticker]
        shares = round(balance * weight / reference[ticker], 2)
        rows.append(
            {
                "ticker": ticker,
                "weight": round(weight, 6),
                "shares": shares,
                "price": round(price, 2),
                "value_cad": round(shares * price, 2),
                "move_pct": round(moves.get(ticker, {}).get("latest_move_pct", 0.0), 2),
            }
        )
    invested = round(sum(r["value_cad"] for r in rows), 2)
    return {
        "persona_id": persona_id,
        "account_type": account_type,
        "refreshed": as_of is not None,
        "invested_cad": invested,
        "cash_cad": cash,
        "total_value_cad": round(invested + cash, 2),
        "holdings": rows,
        "note": "Fictional shares priced in each listing's own currency; FX is ignored.",
        "computed_by": "local-engine",
    }


def sentiment_summary(ticker: str, half_life_days: float | None = None) -> Dict[str, Any]:
    """Deterministic sentiment evidence for one ticker (the Bedrock bridge's only data source).

    Uses the live market window once refreshed, otherwise all headlines to date.
    Scores come from precomputed headline columns; nothing is estimated here.
    """
    data = _data()
    known = {r["ticker"] for r in data["current"]}
    if ticker not in known:
        raise ValueError(f"unknown ticker: {ticker}")
    as_of = _latest() or max(n["date"] for n in data["news"] if n["date"] <= max(r["date"] for r in data["current"]))
    since = min(n["date"] for n in data["news"])
    if as_of is not None and _STATE["refreshed"]:
        since = min(data["dates"])
    rows = [n for n in data["news"] if n["ticker"] == ticker and since <= n["date"] <= as_of]
    peer = sentiment_tools.peer_sentiment(data["news"], ticker, _peers(), since, as_of, half_life_days)
    return {
        "ticker": ticker,
        "as_of": as_of,
        "headline_count": len(rows),
        "mean_sentiment": _round(sentiment_tools.weighted_sentiment(rows, as_of)),
        "recency_weighted_sentiment": _round(
            sentiment_tools.weighted_sentiment(rows, as_of, half_life_days or sentiment_tools.DEFAULT_HALF_LIFE_DAYS)
        ),
        "peer_sentiment": _round(peer["peer_sentiment"]),
        "peers_with_news": peer["peers_with_news"],
        "categories": sentiment_tools.category_breakdown(rows),
        "headlines": [
            {"date": n["date"], "headline": n["headline"], "sentiment": n.get("sentiment") or None, "category": sentiment_tools.row_category(n)}
            for n in sorted(rows, key=lambda n: n["date"])
        ],
        "computed_by": "local-engine",
    }


def _round(value: float | None) -> float | None:
    return None if value is None else round(value, 2)


def _last_price(ticker: str) -> float:
    as_of = _latest()
    price = 0.0
    for row in _data()["current"]:
        if row["ticker"] == ticker:
            price = float(row["close"])
    if as_of:
        for row in _data()["change"]:
            if row["ticker"] == ticker and row["date"] <= as_of:
                price = float(row["close"])
    return price


def position(persona_id: str, ticker: str, action: str) -> Dict[str, Any]:
    """What the investor holds in ``ticker`` and a sample trade (10% of the holding, at least 1 share).

    Mirrors the Holdings panel's default trade size. It reads the persona's starting
    portfolio repriced on the live market; trades simulated in the browser are not included.
    """
    book = portfolio(persona_id)
    row = next((h for h in book["holdings"] if h["ticker"] == ticker), None)
    shares = row["shares"] if row else 0.0
    price = row["price"] if row else round(_last_price(ticker), 2)
    qty = max(1.0, round(shares * 0.1))
    if action == "sell":
        qty = min(qty, shares)
    amount = round(qty * price, 2)
    total = book["total_value_cad"]
    cash_after = book["cash_cad"] + (amount if action == "sell" else -amount)
    return {
        "ticker": ticker,
        "action": action,
        "holds": shares > 0,
        "shares_held": shares,
        "price": price,
        "holding_pct": round(shares * price / total * 100, 1) if total else 0.0,
        "sample_qty": qty,
        "sample_amount_cad": amount,
        "portfolio_pct": round(amount / total * 100, 1) if total else 0.0,
        "cash_after_cad": round(cash_after, 2),
        "affordable": action == "sell" or cash_after >= 0,
        "computed_by": "local-engine",
    }
