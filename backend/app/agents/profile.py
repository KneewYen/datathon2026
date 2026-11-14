"""Investor profile lookup and account recommendation helpers."""

import re
from typing import Any, Dict, Optional
from app.domain.presets import PERSONAS
from app.profiles import HORIZONS, PROFILES

ACCOUNT_BY_HORIZON = {
    "short": ("Non-registered", "Full flexibility and no contribution limit, so money is available when you need it."),
    "mid": ("TFSA", "Tax-free growth and withdrawals fit a medium horizon."),
    "long": ("RRSP", "Tax-deductible contributions and tax-deferred growth suit long-term and retirement goals."),
}


def get_persona(persona_id: str) -> dict:
    try:
        return PERSONAS[persona_id]
    except KeyError as exc:
        raise ValueError(f"unknown persona: {persona_id}") from exc


def parse_horizon(text: str) -> Optional[str]:
    lowered = text.lower()
    if re.search(r"short|soon|near", lowered):
        return "short"
    if re.search(r"\bmid|medium", lowered):
        return "mid"
    if re.search(r"long|retire", lowered):
        return "long"
    match = re.search(r"(\d+)\s*(?:years|yrs|year)", lowered)
    if match:
        years = int(match.group(1))
        return "short" if years <= 5 else "mid" if years <= 12 else "long"
    return None


def parse_risk(text: str) -> Optional[str]:
    lowered = text.lower()
    if re.search(r"low|conservative|safe|cautious", lowered):
        return "conservative"
    if re.search(r"moderate|balanced|medium risk", lowered):
        return "balanced"
    if re.search(r"high|aggressive|growth", lowered):
        return "growth"
    return None


def recommend(text: str) -> Dict[str, Any]:
    lowered = text.lower()
    horizon = parse_horizon(lowered)
    if "home" in lowered or "house" in lowered or "fhsa" in lowered:
        account_type, reason = "FHSA", "Built for a first home purchase: deductible contributions and tax-free withdrawals for the home."
        horizon = horizon or "short"
    elif horizon:
        account_type, reason = ACCOUNT_BY_HORIZON[horizon]
    else:
        return {"needs": "horizon"}
    risk = parse_risk(lowered) or HORIZONS[horizon]["default_risk"]
    profile = PROFILES[risk]
    return {
        "account_type": account_type,
        "horizon": horizon,
        "horizon_label": HORIZONS[horizon]["label"],
        "risk": risk,
        "risk_label": profile["label"],
        "persona": profile["persona"],
        "reason": reason,
    }
