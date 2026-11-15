"""Asset metadata from the starter universe and deterministic allocation arithmetic.

Sector and asset-class facts come from assets_universe.csv, so ESG and crypto
controls can cite a data source instead of an opinion.
"""

from __future__ import annotations

import csv
import os
from functools import lru_cache
from pathlib import Path
from typing import Dict, Mapping

from app.domain.presets import STRATEGY_HOLDINGS

DEFAULT_DATA_DIR = Path(__file__).resolve().parents[3] / "hackathon_info" / "alphaforge_starter"
UNIVERSE_SOURCE = "assets_universe.csv (AlphaForge starter dataset)"


def _data_dir() -> Path:
    return Path(os.getenv("STARTER_DATA_DIR", DEFAULT_DATA_DIR))


@lru_cache(maxsize=1)
def assets() -> Dict[str, Dict[str, str]]:
    with (_data_dir() / "assets_universe.csv").open(newline="", encoding="utf-8") as handle:
        return {row["ticker"]: row for row in csv.DictReader(handle)}


def single_strategy(ticker: str) -> str:
    return f"single_{ticker}"


def holdings_for(allocations: Mapping[str, float]) -> Dict[str, Dict[str, float]]:
    """Strategy baskets for an allocation, including single-asset sleeves."""
    holdings: Dict[str, Dict[str, float]] = {}
    for name in allocations:
        if name in STRATEGY_HOLDINGS:
            holdings[name] = STRATEGY_HOLDINGS[name]
        elif name.startswith("single_") and name[len("single_"):] in assets():
            holdings[name] = {name[len("single_"):]: 1.0}
        else:
            raise ValueError(f"unknown strategy: {name}")
    return holdings


def asset_weights(allocations: Mapping[str, float]) -> Dict[str, float]:
    weights: Dict[str, float] = {}
    holdings = holdings_for(allocations)
    for strategy, allocation in allocations.items():
        for ticker, weight in holdings[strategy].items():
            weights[ticker] = weights.get(ticker, 0.0) + allocation * weight
    return {ticker: weight for ticker, weight in weights.items() if weight > 1e-12}


def crypto_weight(weights: Mapping[str, float]) -> float:
    return sum(w for t, w in weights.items() if assets().get(t, {}).get("asset_class") == "crypto")


def holdings_in_sectors(weights: Mapping[str, float], sectors: list[str]) -> Dict[str, float]:
    return {
        ticker: weight
        for ticker, weight in weights.items()
        if assets().get(ticker, {}).get("sector") in sectors
    }
