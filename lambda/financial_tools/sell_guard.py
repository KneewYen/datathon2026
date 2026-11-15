"""Deterministic sell-guard signals: does the market data support selling a stock?

Pure functions over plain rows so they run the same locally, in tests and inside
AWS Lambda. Nothing here calls a model. News sentiment, when present, arrives as
a precomputed score per headline (from Comprehend, Bedrock or FinBERT) and is
reported as evidence, never used to invent a number.

Verdicts if the investor SELLS now:
  no_signal           the move is too small or volume too normal to matter
  panic_risk          sharp drop on heavy volume, driven by market-wide news
  evidence_supported  sharp drop on heavy volume, news about the company is negative
  mixed               sharp drop on heavy volume, but the causes are unclear

Verdicts if the investor BUYS now:
  no_signal           the move is too small or volume too normal to matter
  chasing_risk        sharp rise on heavy volume with upbeat headlines (buying the hype)
  falling_knife       sharp drop on heavy volume driven by negative company news
  dip_with_context    sharp drop on heavy volume driven by market-wide news
  mixed               sharp move on heavy volume, but the causes are unclear
"""

from __future__ import annotations

import statistics
from datetime import date
from typing import Any, Dict, Iterable, List, Mapping, Sequence

FORMULA_VERSION = "trade-guard-v3"

DROP_THRESHOLD_PCT = -3.0  # trough versus the last pre-event close
VOLUME_SPIKE_RATIO = 1.5  # event volume versus the typical (median) volume
BREADTH_PANIC_SHARE = 0.30  # share of tracked tickers that also dropped sharply
COMPANY_NEWS_SHARE = 0.50  # headlines are "about the company" only if MORE than this share is
RISE_THRESHOLD_PCT = 3.0  # peak versus the last pre-event close, for buy checks
# Scoring scales: the value at which each signal counts as "full strength".
FULL_VOLUME_EXCESS = 3.0  # volume at 1 + this many times typical = full intensity
FULL_REBOUND_PCT = 5.0  # a rebound this large means the drop was not lasting
FULL_RISE_PCT = 6.0  # a rally this large is full price momentum
NET_DECISION_MARGIN = 0.15  # fundamental minus emotion must beat this to pick a side
HYPE_THRESHOLD = 0.55  # hype score at or above this means chasing
TYPICAL_VOLUME_DAYS = 20


def _day(value: str | date) -> date:
    return value if isinstance(value, date) else date.fromisoformat(value)


def _by_ticker(prices: Iterable[Mapping[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    grouped: Dict[str, List[Dict[str, Any]]] = {}
    for row in prices:
        grouped.setdefault(row["ticker"], []).append(
            {
                "date": _day(row["date"]),
                "close": float(row["close"]),
                "volume": float(row["volume"]),
            }
        )
    for rows in grouped.values():
        rows.sort(key=lambda r: r["date"])
    return grouped


def price_volume_signals(
    current_prices: Iterable[Mapping[str, Any]],
    change_prices: Iterable[Mapping[str, Any]],
    as_of: str | date,
) -> Dict[str, Dict[str, float]]:
    """Per-ticker drop, volume ratio and rebound using change rows up to ``as_of``."""
    cutoff = _day(as_of)
    current = _by_ticker(current_prices)
    change = _by_ticker(change_prices)
    signals: Dict[str, Dict[str, float]] = {}
    for ticker, history in current.items():
        window = [r for r in change.get(ticker, []) if r["date"] <= cutoff]
        if not window:
            continue
        reference_close = history[-1]["close"]
        typical_volume = statistics.median(r["volume"] for r in history[-TYPICAL_VOLUME_DAYS:])
        trough = min(r["close"] for r in window)
        peak = max(r["close"] for r in window)
        latest = window[-1]["close"]
        peak_volume = max(r["volume"] for r in window)
        signals[ticker] = {
            "drop_pct": (trough / reference_close - 1) * 100,
            "rise_pct": (peak / reference_close - 1) * 100,
            "latest_move_pct": (latest / reference_close - 1) * 100,
            "rebound_from_trough_pct": (latest / trough - 1) * 100,
            "volume_ratio": peak_volume / typical_volume,
            "days_observed": float(len(window)),
        }
    return signals


def news_signals(
    news: Iterable[Mapping[str, Any]], ticker: str, since: str | date, as_of: str | date
) -> Dict[str, float | None]:
    """Headline counts by scope and optional mean sentiment for one ticker.

    Only headlines from ``since`` (the first day of the market change) through
    ``as_of`` count, so calm background news does not dilute the event window.
    """
    start, cutoff = _day(since), _day(as_of)
    rows = [n for n in news if n["ticker"] == ticker and start <= _day(n["date"]) <= cutoff]
    company = sum(1 for n in rows if n.get("scope") == "company")
    scores = [float(n["sentiment"]) for n in rows if n.get("sentiment") not in (None, "")]
    return {
        "headline_count": float(len(rows)),
        "company_news_share": company / len(rows) if rows else 0.0,
        "mean_sentiment": statistics.fmean(scores) if scores else None,
    }


def breadth(signals: Mapping[str, Mapping[str, float]]) -> float:
    """Share of tracked tickers that fell at least as much as the drop threshold."""
    if not signals:
        return 0.0
    hit = sum(1 for s in signals.values() if s["drop_pct"] <= DROP_THRESHOLD_PCT)
    return hit / len(signals)


def _clip(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def score_signals(
    rise_pct: float,
    volume_ratio: float,
    rebound_pct: float,
    company_news_share: float,
    market_breadth: float,
    sentiment: float | None,
) -> Dict[str, float]:
    """Turn the raw market signals into three 0..1 scores.

    fundamental  evidence that the move is about the company and will last:
                 0.5 * share of company headlines
                 0.3 * how negative the headline sentiment is
                 0.2 * how little the price has rebounded
    emotion      evidence that the move is market-driven or crowd-driven:
                 0.4 * share of headlines that are market-wide
                 0.3 * share of tracked tickers falling together
                 0.3 * how far volume is above normal
    hype         evidence of a rally fuelled by enthusiasm:
                 0.4 * how upbeat the headline sentiment is
                 0.3 * how far volume is above normal
                 0.3 * the size of the rise
    Missing sentiment counts as neutral (0), so the score never invents it.
    """
    s = 0.0 if sentiment is None else _clip(sentiment, -1.0, 1.0)
    intensity = _clip((volume_ratio - 1.0) / FULL_VOLUME_EXCESS)
    rebound = _clip(rebound_pct / FULL_REBOUND_PCT)
    return {
        "fundamental": 0.5 * company_news_share + 0.3 * _clip(-s) + 0.2 * (1.0 - rebound),
        "emotion": 0.4 * (1.0 - company_news_share) + 0.3 * market_breadth + 0.3 * intensity,
        "hype": 0.4 * _clip(s) + 0.3 * intensity + 0.3 * _clip(rise_pct / FULL_RISE_PCT),
    }


def decide(
    action: str,
    drop_pct: float,
    rise_pct: float,
    volume_ratio: float,
    scores: Mapping[str, float],
) -> Dict[str, Any]:
    """Categorise the action from the scores and report the score that decided it.

    Gate: nothing is flagged unless volume is at least VOLUME_SPIKE_RATIO times normal
    and the price moved at least 3% against (drop) or with (rise) the investor.

    SELL  a drop is judged by net = fundamental - emotion:
            net >=  margin -> evidence_supported   (the data backs the concern)
            net <= -margin -> panic_risk           (market- or crowd-driven)
            otherwise      -> mixed
    BUY   a rise is judged by the hype score (>= HYPE_THRESHOLD -> chasing_risk);
          a drop uses the same net as a sell:
            net >=  margin -> falling_knife        (company trouble)
            net <= -margin -> dip_with_context     (market-driven dip)
            otherwise      -> mixed
    """
    net = scores["fundamental"] - scores["emotion"]
    heavy = volume_ratio >= VOLUME_SPIKE_RATIO
    dropped = drop_pct <= DROP_THRESHOLD_PCT
    rose = rise_pct >= RISE_THRESHOLD_PCT and not dropped

    def split(high: str, low: str) -> str:
        return high if net >= NET_DECISION_MARGIN else low if net <= -NET_DECISION_MARGIN else "mixed"

    def balance_score() -> Dict[str, Any]:
        return {
            "name": "Company-driven vs market-driven",
            "value": round(50 + 50 * net, 1),
            "low_label": "Market- or crowd-driven",
            "high_label": "Company-driven",
        }

    if not heavy:
        return {"verdict": "no_signal", "score": None}
    if action == "sell":
        if dropped:
            return {"verdict": split("evidence_supported", "panic_risk"), "score": balance_score()}
        return {"verdict": "no_signal", "score": None}
    if rose:
        verdict = "chasing_risk" if scores["hype"] >= HYPE_THRESHOLD else "mixed"
        return {
            "verdict": verdict,
            "score": {
                "name": "Hype",
                "value": round(100 * scores["hype"], 1),
                "low_label": "Calm",
                "high_label": "Hype",
            },
        }
    if dropped:
        return {"verdict": split("falling_knife", "dip_with_context"), "score": balance_score()}
    return {"verdict": "no_signal", "score": None}


def _evidence(
    ticker: str, key: str, label: str, value: float | None, unit: str, source: str
) -> Dict[str, Any]:
    return {
        "evidence_id": f"{ticker}:{key}",
        "label": label,
        "value": None if value is None else round(value, 4),
        "unit": unit,
        "source": source,
        "formula_version": FORMULA_VERSION,
    }


def evaluate_trade(
    action: str,
    ticker: str,
    current_prices: Sequence[Mapping[str, Any]],
    change_prices: Sequence[Mapping[str, Any]],
    news: Sequence[Mapping[str, Any]],
    as_of: str | date,
) -> Dict[str, Any]:
    """Verdict and evidence for a buy or sell of ``ticker`` on ``as_of``."""
    if action not in ("buy", "sell"):
        raise ValueError("action must be buy or sell")
    signals = price_volume_signals(current_prices, change_prices, as_of)
    if ticker not in signals:
        raise ValueError(f"no market-change data for {ticker} on or before {as_of}")
    own = signals[ticker]
    since = min(_day(r["date"]) for r in change_prices)
    story = news_signals(news, ticker, since, as_of)
    market_breadth = breadth(signals)
    company_share = float(story["company_news_share"] or 0.0)
    sentiment = story["mean_sentiment"]
    scores = score_signals(
        own["rise_pct"],
        own["volume_ratio"],
        own["rebound_from_trough_pct"],
        company_share,
        market_breadth,
        sentiment,
    )
    decision = decide(action, own["drop_pct"], own["rise_pct"], own["volume_ratio"], scores)
    verdict = decision["verdict"]
    evidence = [
        _evidence(ticker, "drop", "Drop from last close to trough", own["drop_pct"], "percent", "prices"),
        _evidence(ticker, "rise", "Rise from last close to peak", own["rise_pct"], "percent", "prices"),
        _evidence(ticker, "volume", "Peak volume vs typical volume", own["volume_ratio"], "x", "prices"),
        _evidence(ticker, "rebound", "Rebound from trough", own["rebound_from_trough_pct"], "percent", "prices"),
        _evidence(ticker, "breadth", "Tracked tickers also down sharply", market_breadth * 100, "percent", "prices"),
        _evidence(ticker, "company_news", "Headlines about the company itself", company_share * 100, "percent", "news"),
        _evidence(ticker, "sentiment", "Mean headline sentiment", sentiment, "score", "news"),
        _evidence(ticker, "fundamental", "Company-driven score", scores["fundamental"] * 100, "points", "model"),
        _evidence(ticker, "emotion", "Market-driven score", scores["emotion"] * 100, "points", "model"),
        _evidence(ticker, "hype", "Hype score", scores["hype"] * 100, "points", "model"),
    ]
    return {
        "status": "ok",
        "operation": "evaluate_trade",
        "action": action,
        "ticker": ticker,
        "as_of": _day(as_of).isoformat(),
        "verdict": verdict,
        "score": decision["score"],
        "sentiment": None if sentiment is None else round(sentiment, 2),
        "sentiment_label": None
        if sentiment is None
        else "upbeat" if sentiment >= 0.3 else "negative" if sentiment <= -0.3 else "neutral",
        "evidence": evidence,
        "limitations": [
            "Verdicts describe how the market data looks; they are not advice or a forecast.",
            "Sentiment is missing until headlines are scored."
            if sentiment is None
            else "Sentiment and headline scope come from a model score and are shown as evidence.",
        ],
        "formula_version": FORMULA_VERSION,
    }


def evaluate_sell(*args: Any, **kwargs: Any) -> Dict[str, Any]:
    """Backward-compatible wrapper: ``evaluate_sell(ticker, ...)``."""
    return evaluate_trade("sell", *args, **kwargs)
