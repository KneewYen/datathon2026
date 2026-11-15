from __future__ import annotations

import re
from typing import Dict, List, Tuple

from app.domain.models import InvestmentIntent


TICKER_ALIASES = {
    "NVIDIA": "NVDA",
    "NVIDIA CORP": "NVDA",
    "NVDA": "NVDA",
}


def parse_investment_intent(
    question: str, accounts: List[Dict]
) -> Tuple[InvestmentIntent | None, str | None]:
    text = question.upper().replace("C$", "$ ")
    ticker = next((ticker for alias, ticker in TICKER_ALIASES.items() if alias in text), None)
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
