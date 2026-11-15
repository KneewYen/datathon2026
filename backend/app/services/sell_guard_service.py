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

from app.domain.presets import PERSONAS, STRATEGY_HOLDINGS

ROOT = Path(__file__).resolve().parents[3]
SIM = ROOT / "data" / "simulated"
sys.path.insert(0, str(ROOT / "lambda" / "financial_tools"))

import sell_guard  # noqa: E402  (shared with the AWS Lambda package)


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
    result = sell_guard.evaluate_trade(action, ticker, data["current"], data["change"], data["news"], as_of)
    result["computed_by"] = "local-engine"
    return result


def holdings(persona_id: str) -> List[Dict[str, Any]]:
    """Each ticker's weight in the persona's default allocation."""
    persona = PERSONAS[persona_id]
    weights: Dict[str, float] = {}
    for strategy, share in persona["default_allocations"].items():
        for ticker, weight in STRATEGY_HOLDINGS.get(strategy, {}).items():
            weights[ticker] = weights.get(ticker, 0.0) + share * weight
    return [{"ticker": t, "weight": w} for t, w in sorted(weights.items(), key=lambda kv: -kv[1])]


def portfolio(persona_id: str) -> Dict[str, Any]:
    """Fictional positions: shares are sized at the last pre-event close, then repriced."""
    as_of = _latest()
    persona = PERSONAS[persona_id]
    balance = float(persona["starting_balance_cad"])
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
    for item in holdings(persona_id):
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
    cash = float(persona["starting_cash_cad"])
    return {
        "persona_id": persona_id,
        "refreshed": as_of is not None,
        "invested_cad": invested,
        "cash_cad": cash,
        "total_value_cad": round(invested + cash, 2),
        "holdings": rows,
        "note": "Fictional shares priced in each listing's own currency; FX is ignored.",
        "computed_by": "local-engine",
    }
