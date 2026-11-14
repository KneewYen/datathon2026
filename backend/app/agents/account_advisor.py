"""Account Advisor Agent: recommends an account type and risk profile."""
import re
from typing import Any, Dict, Optional

from app.profiles import HORIZONS, PROFILES

ACCOUNT_BY_HORIZON = {
    "short": ("Non-registered", "Full flexibility and no contribution limit, so money is available when you need it."),
    "mid": ("TFSA", "Tax-free growth and withdrawals fit a medium horizon."),
    "long": ("RRSP", "Tax-deductible contributions and tax-deferred growth suit long-term and retirement goals."),
}


def parse_horizon(text: str) -> Optional[str]:
    t = text.lower()
    if re.search(r"short|soon|near", t):
        return "short"
    if re.search(r"\bmid|medium", t):
        return "mid"
    if re.search(r"long|retire", t):
        return "long"
    m = re.search(r"(\d+)\s*(?:years|yrs|year)", t)
    if m:
        y = int(m.group(1))
        return "short" if y <= 5 else "mid" if y <= 12 else "long"
    return None


def parse_risk(text: str) -> Optional[str]:
    t = text.lower()
    if re.search(r"low|conservative|safe|cautious", t):
        return "conservative"
    if re.search(r"moderate|balanced|medium risk", t):
        return "balanced"
    if re.search(r"high|aggressive|growth", t):
        return "growth"
    return None


def recommend(text: str) -> Dict[str, Any]:
    t = text.lower()
    horizon = parse_horizon(t)
    if "home" in t or "house" in t or "fhsa" in t:
        account_type, why = "FHSA", "Built for a first home purchase: deductible contributions and tax-free withdrawals for the home."
        horizon = horizon or "short"
    elif horizon:
        account_type, why = ACCOUNT_BY_HORIZON[horizon]
    else:
        return {"needs": "horizon"}

    risk = parse_risk(t) or HORIZONS[horizon]["default_risk"]
    p = PROFILES[risk]
    return {
        "account_type": account_type,
        "horizon": horizon,
        "horizon_label": HORIZONS[horizon]["label"],
        "risk": risk,
        "risk_label": p["label"],
        "persona": p["persona"],
        "reason": why,
    }
