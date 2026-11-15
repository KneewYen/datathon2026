"""Risk profiles, each based on a case persona."""

PROFILES = {
    "conservative": {
        "label": "Conservative",
        "persona": "Robert",
        "horizon": "short",
        "horizon_profile": "Short-term profile",
        "strategies": ["Capital preservation", "Quality", "Dividend"],
    },
    "balanced": {
        "label": "Balanced",
        "persona": "Mateo",
        "horizon": "mid",
        "horizon_profile": "Mid-term profile",
        "strategies": ["Balanced index", "ESG", "Dividend"],
    },
    "growth": {
        "label": "Growth",
        "persona": "Amira",
        "horizon": "long",
        "horizon_profile": "Long-term profile",
        "strategies": ["Growth", "Momentum", "Crypto (capped)"],
    },
}

HORIZONS = {
    "short": {"label": "Short term (3-5 yrs)", "default_risk": "conservative"},
    "mid": {"label": "Mid term (8-12 yrs)", "default_risk": "balanced"},
    "long": {"label": "Long term (15+ yrs)", "default_risk": "growth"},
}