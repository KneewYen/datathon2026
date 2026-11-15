from __future__ import annotations

from typing import Any, Dict


# Fictional risk budgets: a documented, deterministic policy per persona, not advice.
# max_months_underwater is half of the persona's minimum horizon, so a 2022-style
# recovery must fit comfortably inside the time the money is invested.
PERSONAS: Dict[str, Dict[str, Any]] = {
    "amira": {
        "name": "Amira",
        "age": 26,
        "risk": "high",
        "horizon_years": "15+",
        "objective": "long-term capital growth with diversification",
        "preferences": ["AI and technology", "crypto", "diversification"],
        "account_type": "TFSA",
        "portfolio_value": 25_000,
        "risk_budget": {
            "max_stress_drawdown": -0.40,
            "single_position_cap": 0.15,
            "crypto_cap": 0.10,
            "max_months_underwater": 90,
        },
        "alternative_strategy": "growth",
        "esg_excluded_sectors": [],
    },
    "mateo": {
        "name": "Mateo",
        "age": 41,
        "risk": "moderate",
        "horizon_years": "8-12",
        "objective": "balanced growth with stability",
        "preferences": ["ESG", "limited speculation", "diversification"],
        "account_type": "TFSA",
        "portfolio_value": 120_000,
        "risk_budget": {
            "max_stress_drawdown": -0.25,
            "single_position_cap": 0.05,
            "crypto_cap": 0.0,
            "max_months_underwater": 48,
        },
        "alternative_strategy": "esg",
        "esg_excluded_sectors": ["Energy"],
    },
    "robert": {
        "name": "Robert",
        "age": 59,
        "risk": "low-moderate",
        "horizon_years": "3-5",
        "objective": "capital preservation with some growth",
        "preferences": ["quality companies", "stability", "no crypto"],
        "account_type": "RRSP",
        "portfolio_value": 450_000,
        "risk_budget": {
            "max_stress_drawdown": -0.15,
            "single_position_cap": 0.05,
            "crypto_cap": 0.0,
            "max_months_underwater": 18,
        },
        "alternative_strategy": "quality",
        "esg_excluded_sectors": [],
    },
}


STRATEGY_HOLDINGS: Dict[str, Dict[str, float]] = {
    "growth": {"QQQ": 0.35, "NVDA": 0.25, "SHOP.TO": 0.20, "SPY": 0.20},
    "dividend": {"XIU.TO": 0.30, "ENB.TO": 0.25, "FTS.TO": 0.25, "PG": 0.20},
    "momentum": {"QQQ": 0.40, "SPY": 0.30, "XIU.TO": 0.30},
    "preservation": {"ZST.TO": 0.40, "XBB.TO": 0.30, "GLD": 0.20, "PG": 0.10},
    "esg": {"ESGV": 0.70, "FTS.TO": 0.15, "CNR.TO": 0.15},
    "quality": {"CNR.TO": 0.25, "CSU.TO": 0.20, "MSFT": 0.20, "JNJ": 0.20, "PG": 0.15},
    "balanced_index": {"XIU.TO": 0.30, "SPY": 0.30, "XBB.TO": 0.25, "AGG": 0.15},
    "crypto": {"BTC-USD": 0.70, "ETH-USD": 0.30},
}

STRATEGY_LABELS = {
    "growth": "Growth",
    "dividend": "Dividend",
    "momentum": "Momentum",
    "preservation": "Capital preservation",
    "esg": "ESG",
    "quality": "Quality",
    "balanced_index": "Balanced index",
    "crypto": "Crypto",
}


# Each persona gets a scenario that tests what the case brief says that persona tests.
PERSONA_SCENARIOS: Dict[str, Dict[str, Any]] = {
    "amira": {
        "question": (
            "Would moving 20% of my TFSA from my tech-heavy growth strategy into a broad "
            "index strategy diversify me without abandoning growth?"
        ),
        "account_type": "TFSA",
        "strategy_allocations": {
            "growth": 0.40,
            "momentum": 0.20,
            "crypto": 0.10,
            "dividend": 0.15,
            "balanced_index": 0.15,
        },
        "shift": {"from_strategy": "growth", "to_strategy": "balanced_index", "amount": 0.20},
        "portfolio_value": 25_000,
    },
    "mateo": {
        "question": (
            "Would moving my 30% dividend sleeve into the ESG strategy keep my balance "
            "while removing fossil-fuel holdings?"
        ),
        "account_type": "TFSA",
        "strategy_allocations": {
            "balanced_index": 0.40,
            "dividend": 0.30,
            "growth": 0.20,
            "esg": 0.10,
        },
        "shift": {"from_strategy": "dividend", "to_strategy": "esg", "amount": 0.30},
        "portfolio_value": 120_000,
    },
    "robert": {
        "question": (
            "Would moving 15% of my RRSP from capital preservation into the growth strategy "
            "be reasonable three to five years before retirement?"
        ),
        "account_type": "RRSP",
        "strategy_allocations": {
            "preservation": 0.45,
            "quality": 0.30,
            "dividend": 0.25,
            "growth": 0.0,
        },
        "shift": {"from_strategy": "preservation", "to_strategy": "growth", "amount": 0.15},
        "portfolio_value": 450_000,
    },
}

CHALLENGE_PROMPTS: Dict[str, list[str]] = {
    "amira": ["Put 25% of my TFSA in NVDA", "Add 20% bitcoin", "Should I buy Tesla?"],
    "mateo": ["Put 10% in Exxon", "Should I buy NVDA?", "Add 5% Ethereum"],
    "robert": ["Put 25% of my RRSP in NVDA", "Should I buy Tesla now?", "Add 10% bitcoin"],
}

# Portfolio each persona holds when making a specific request. Mateo's is his
# ESG-screened allocation (after his scenario's shift), so the screen starts clean.
CHALLENGE_BASELINES: Dict[str, Dict[str, Any]] = {
    "amira": {
        "description": "Amira's current growth-oriented TFSA.",
        "strategy_allocations": dict(PERSONA_SCENARIOS["amira"]["strategy_allocations"]),
    },
    "mateo": {
        "description": "Mateo's ESG-screened TFSA (dividend sleeve already moved into ESG).",
        "strategy_allocations": {"balanced_index": 0.40, "esg": 0.40, "growth": 0.20},
    },
    "robert": {
        "description": "Robert's current preservation-first RRSP.",
        "strategy_allocations": dict(PERSONA_SCENARIOS["robert"]["strategy_allocations"]),
    },
}
