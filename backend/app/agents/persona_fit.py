"""Persona Fit: how a verdict lands for one fictional investor, and why.

Rule-based and deterministic (no model call). It reads the investor's risk level, horizon and
goal, whether the stock is growth-style or steady, and the guard's verdict, then returns a
stance ("fits your plan", "wait and watch", "be careful") with the reasons behind it. It
describes fit with the profile in a simulation; it is not advice.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from app import i18n
from app.domain.presets import PERSONAS, STRATEGY_HOLDINGS

BAND = {"high": "high", "moderate": "moderate", "low-moderate": "low"}
RISK_LABEL = {
    "high": ("High", "Élevé"),
    "moderate": ("Moderate", "Modéré"),
    "low": ("Low to moderate", "Faible à modéré"),
}
GOAL_FR = {
    "amira": "croissance du capital à long terme avec diversification",
    "mateo": "croissance équilibrée avec stabilité",
    "robert": "préservation du capital avec un peu de croissance",
}

# (action, verdict) -> (stance, headline_en, headline_fr)
HOW: Dict[tuple, tuple] = {
    ("sell", "panic_risk"): ("wait", "Hold for now and let the market settle before selling.", "Attendre que le marché se calme avant de vendre."),
    ("sell", "evidence_supported"): ("fits", "Selling fits your plan: the trouble looks specific to this company.", "Vendre cadre avec votre plan : le problème semble propre à cette entreprise."),
    ("sell", "mixed"): ("wait", "Wait and watch: the signals do not agree yet.", "Attendre et observer : les signaux ne concordent pas encore."),
    ("sell", "no_signal"): ("fits", "Nothing unusual, so there is no urgent reason to act either way.", "Rien d'inhabituel : aucune urgence d'agir dans un sens ou dans l'autre."),
    ("buy", "dip_with_context"): ("fits", "Buying this market-wide dip fits your plan.", "Acheter ce recul de tout le marché cadre avec votre plan."),
    ("buy", "chasing_risk"): ("careful", "Be careful: waiting for the excitement to cool is safer than buying into hype.", "Prudence : mieux vaut attendre que l'enthousiasme retombe que d'acheter par engouement."),
    ("buy", "falling_knife"): ("careful", "Avoid for now: the company itself is in trouble and has not started to recover.", "À éviter pour l'instant : l'entreprise elle-même est en difficulté et ne remonte pas encore."),
    ("buy", "mixed"): ("wait", "Wait and watch: the signals do not agree yet.", "Attendre et observer : les signaux ne concordent pas encore."),
    ("buy", "no_signal"): ("fits", "Nothing unusual, so buying is not blocked by the market data.", "Rien d'inhabituel : les données de marché ne s'opposent pas à l'achat."),
}

# Stance tweaks by risk band: (action, verdict, band) -> stance
OVERRIDE = {
    ("buy", "chasing_risk", "high"): "wait",
}

# Extra reason by (action, verdict, band)
BAND_REASON: Dict[tuple, tuple] = {
    ("sell", "panic_risk", "high"): ("A long horizon means you can ride out a market-wide dip.", "Un horizon long vous permet d'attendre la fin d'un recul de tout le marché."),
    ("sell", "panic_risk", "moderate"): ("You have time to wait for the market to settle.", "Vous avez le temps d'attendre que le marché se calme."),
    ("sell", "panic_risk", "low"): ("Your horizon is shorter, so if you need this money soon, selling a small part can still make sense.", "Votre horizon est plus court : si vous avez bientôt besoin de cet argent, en vendre une petite partie peut quand même avoir du sens."),
    ("sell", "evidence_supported", "low"): ("Protecting what you have is your priority.", "Protéger ce que vous avez est votre priorité."),
    ("sell", "evidence_supported", "moderate"): ("Balanced growth with stability: cutting a troubled holding fits.", "Croissance équilibrée avec stabilité : alléger un titre en difficulté est cohérent."),
    ("sell", "evidence_supported", "high"): ("You can afford to trim a troubled holding and move on.", "Vous pouvez vous permettre d'alléger un titre en difficulté."),
    ("buy", "dip_with_context", "moderate"): ("Buying in small steps keeps the risk balanced.", "Acheter par petites étapes garde le risque équilibré."),
    ("buy", "dip_with_context", "high"): ("Dips are where a long-term growth plan adds shares cheaply.", "Les reculs sont l'occasion d'ajouter des titres à bon prix dans un plan de croissance à long terme."),
    ("buy", "chasing_risk", "high"): ("Even long-term investors overpay when they buy into hype.", "Même les investisseurs à long terme paient trop cher quand ils achètent par engouement."),
    ("buy", "chasing_risk", "moderate"): ("Your plan limits speculation, and hype is speculation.", "Votre plan limite la spéculation, et l'engouement en est une."),
    ("buy", "chasing_risk", "low"): ("Your plan avoids speculation, and hype is speculation.", "Votre plan évite la spéculation, et l'engouement en est une."),
    ("buy", "falling_knife", "high"): ("Time is on your side, but there is no need to buy before it recovers.", "Le temps joue pour vous, mais inutile d'acheter avant que ça remonte."),
}


def _horizon_reason(band: str, years: str, lang: str) -> str:
    return {
        "high": i18n.pick(lang, f"You're investing for {years} years, so short-term dips matter less to your goal.", f"Vous investissez pour {years} ans : les reculs à court terme comptent moins pour votre objectif."),
        "moderate": i18n.pick(lang, f"With {years} years ahead you have time, but you also want stability.", f"Avec {years} ans devant vous, vous avez du temps, mais vous voulez aussi de la stabilité."),
        "low": i18n.pick(lang, f"With only {years} years to go, protecting what you have matters more than chasing growth.", f"Avec seulement {years} ans devant vous, protéger ce que vous avez compte plus que de courir après la croissance."),
    }[band]


def _is_growth_style(ticker: str) -> bool:
    groups = {s for s, holdings in STRATEGY_HOLDINGS.items() if ticker in holdings}
    return bool(groups & {"growth", "momentum"}) and not (groups & {"dividend", "preservation"})


def fit(
    persona_id: str, action: str, ticker: str, verdict: str, position: Optional[Dict[str, Any]], lang: str = "en"
) -> Optional[Dict[str, Any]]:
    """Stance, headline and reasons for this investor. None when the persona is unknown."""
    persona = PERSONAS.get(persona_id)
    if not persona:
        return None
    lang = i18n.normalize(lang)
    p = lambda en, fr: i18n.pick(lang, en, fr)  # noqa: E731
    band = BAND[persona["risk"]]
    years = persona["horizon_years"]
    goal = persona["objective"] if lang == "en" else GOAL_FR[persona_id]
    risk_label = RISK_LABEL[band][0 if lang == "en" else 1]
    header = {"id": persona_id, "name": persona["name"], "risk": risk_label, "horizon_years": years, "goal": goal}

    if action == "sell" and position is not None and not position["holds"]:
        return {
            "persona": header,
            "stance": "wait",
            "headline": p(f"There is nothing to sell: you don't hold any {ticker}.", f"Rien à vendre : vous ne détenez aucun titre {ticker}."),
            "why": [],
        }

    stance, en, fr = HOW.get((action, verdict), ("wait", "Wait and watch.", "Attendre et observer."))
    stance = OVERRIDE.get((action, verdict, band), stance)
    why: List[str] = [_horizon_reason(band, years, lang), p(f"Your goal is {goal}.", f"Votre objectif : {goal}.")]
    extra = BAND_REASON.get((action, verdict, band))
    if extra:
        why.append(p(*extra))
    headline = p(en, fr)
    if action == "buy" and _is_growth_style(ticker) and band == "low" and stance == "fits":
        stance = "wait"
        headline = p(
            "The market data allows this buy, but it may not suit you: wait and think about it.",
            "Les données de marché permettent cet achat, mais il pourrait ne pas vous convenir : attendez et réfléchissez.",
        )
        why.append(p(f"{ticker} is a growth-style investment, and you prefer stability.", f"{ticker} est un placement axé sur la croissance, et vous préférez la stabilité."))
    if action == "sell" and position is not None and position.get("holding_pct"):
        why.append(p(f"{ticker} is about {position['holding_pct']}% of your portfolio.", f"{ticker} représente environ {position['holding_pct']} % de votre portefeuille."))
    return {"persona": header, "stance": stance, "headline": headline, "why": why}
