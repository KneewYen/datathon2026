from __future__ import annotations

import re
from typing import Dict, List, Tuple

from app.domain.models import InvestmentIntent


TICKER_ALIASES = {
    "ROYAL BANK OF CANADA": "RY.TO",
    "RBC": "RY.TO",
    "RY.TO": "RY.TO",
    "TORONTO-DOMINION BANK": "TD.TO",
    "TD BANK": "TD.TO",
    "TD.TO": "TD.TO",
    "MANULIFE FINANCIAL": "MFC.TO",
    "MANULIFE": "MFC.TO",
    "MFC.TO": "MFC.TO",
    "ENBRIDGE": "ENB.TO",
    "ENB.TO": "ENB.TO",
    "CANADIAN NATURAL RESOURCES": "CNQ.TO",
    "CNQ.TO": "CNQ.TO",
    "CANADIAN NATIONAL RAILWAY": "CNR.TO",
    "CNR.TO": "CNR.TO",
    "FORTIS": "FTS.TO",
    "FTS.TO": "FTS.TO",
    "ALIMENTATION COUCHE-TARD": "ATD.TO",
    "COUCHE-TARD": "ATD.TO",
    "ATD.TO": "ATD.TO",
    "SHOPIFY": "SHOP.TO",
    "SHOP.TO": "SHOP.TO",
    "CONSTELLATION SOFTWARE": "CSU.TO",
    "CSU.TO": "CSU.TO",
    "APPLE": "AAPL",
    "AAPL": "AAPL",
    "MICROSOFT": "MSFT",
    "MSFT": "MSFT",
    "NVIDIA CORP": "NVDA",
    "NVIDIA": "NVDA",
    "NVDA": "NVDA",
    "ALPHABET": "GOOGL",
    "GOOGLE": "GOOGL",
    "GOOGL": "GOOGL",
    "AMAZON": "AMZN",
    "AMZN": "AMZN",
    "TESLA": "TSLA",
    "TSLA": "TSLA",
    "JPMORGAN CHASE": "JPM",
    "JPMORGAN": "JPM",
    "JPM": "JPM",
    "JOHNSON & JOHNSON": "JNJ",
    "JNJ": "JNJ",
    "PROCTER & GAMBLE": "PG",
    "PROCTER AND GAMBLE": "PG",
    "PG": "PG",
    "EXXON MOBIL": "XOM",
    "XOM": "XOM",
    "XIU.TO": "XIU.TO",
    "SPY": "SPY",
    "QQQ": "QQQ",
    "ESGV": "ESGV",
    "XBB.TO": "XBB.TO",
    "ZST.TO": "ZST.TO",
    "AGG": "AGG",
    "TLT": "TLT",
    "GLD": "GLD",
    "BITCOIN": "BTC-USD",
    "BTC-USD": "BTC-USD",
    "ETHER": "ETH-USD",
    "ETHEREUM": "ETH-USD",
    "ETH-USD": "ETH-USD",
}


def _ticker_from_text(text: str) -> str | None:
    for alias in sorted(TICKER_ALIASES, key=len, reverse=True):
        if re.search(rf"(?<![A-Z0-9]){re.escape(alias)}(?![A-Z0-9])", text):
            return TICKER_ALIASES[alias]
    return None


def parse_investment_intent(
    question: str, accounts: List[Dict]
) -> Tuple[InvestmentIntent | None, str | None]:
    text = question.upper().replace("C$", "$ ")
    ticker = _ticker_from_text(text)
    amount_match = re.search(
        r"(?:\$|CAD\s*)?\s*([0-9]{1,3}(?:,[0-9]{3})+|[0-9]+(?:\.[0-9]+)?)\s*(CAD|USD)?",
        text,
    )
    if not ticker:
        return None, "Which security or ticker would you like to analyze?"
    if not amount_match:
        return None, f"How much would you like to invest in {ticker}, and in which currency?"
    amount = float(amount_match.group(1).replace(",", ""))
    currency = amount_match.group(2) or ("CAD" if "CAD" in text else None)
    if currency not in {"CAD", "USD"}:
        return None, f"Is the {amount:,.2f} purchase amount in CAD or USD?"

    mentioned = [
        account["id"]
        for account in accounts
        if account["type"].upper() in text or account["id"].upper() in text
    ]
    compare_accounts = (
        len(mentioned) > 1
        or "WHICH ACCOUNT" in text
        or "ACROSS" in text
    )
    return (
        InvestmentIntent(
            ticker=ticker,
            amount=amount,
            currency=currency,
            account_ids=mentioned,
            compare_accounts=compare_accounts,
        ),
        None,
    )
