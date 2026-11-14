from __future__ import annotations

from typing import Dict


PERSONAS = {
    "amira": {
        "name": "Amira",
        "age": 26,
        "risk": "high",
        "horizon_years": "15+",
        "objective": "long-term capital growth with diversification",
        "preferences": ["AI and technology", "crypto", "diversification"],
    },
    "mateo": {
        "name": "Mateo",
        "age": 41,
        "risk": "moderate",
        "horizon_years": "8-12",
        "objective": "balanced growth with stability",
        "preferences": ["ESG", "limited speculation", "diversification"],
    },
    "robert": {
        "name": "Robert",
        "age": 59,
        "risk": "low-moderate",
        "horizon_years": "3-5",
        "objective": "capital preservation with some growth",
        "preferences": ["quality companies", "stability", "no crypto"],
    },
}


STRATEGY_HOLDINGS: Dict[str, Dict[str, float]] = {
    "growth": {
        "QQQ": 0.35,
        "NVDA": 0.25,
        "SHOP.TO": 0.20,
        "SPY": 0.20,
    },
    "dividend": {
        "XIU.TO": 0.30,
        "ENB.TO": 0.25,
        "FTS.TO": 0.25,
        "PG": 0.20,
    },
    "momentum": {
        "QQQ": 0.40,
        "SPY": 0.30,
        "XIU.TO": 0.30,
    },
    "preservation": {
        "ZST.TO": 0.40,
        "XBB.TO": 0.30,
        "GLD": 0.20,
        "PG": 0.10,
    },
}
