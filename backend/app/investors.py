from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict


FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures"


def _read_fixture(name: str) -> Dict[str, Any]:
    return json.loads((FIXTURE_DIR / name).read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def investor_fixture() -> Dict[str, Any]:
    fixture = _read_fixture("investor_v1.json")
    if fixture.get("fictional") is not True:
        raise ValueError("investor fixture must be explicitly marked fictional")
    account_ids = [account["id"] for account in fixture["accounts"]]
    if len(account_ids) != len(set(account_ids)):
        raise ValueError("investor fixture contains duplicate account IDs")
    return fixture


@lru_cache(maxsize=1)
def etf_constituent_fixture() -> Dict[str, Any]:
    fixture = _read_fixture("etf_constituents_v1.json")
    if fixture.get("offline_fixture") is not True:
        raise ValueError("ETF constituent fixture must disclose offline status")
    return fixture


def get_investor(investor_id: str) -> Dict[str, Any]:
    fixture = investor_fixture()
    if fixture["investor"]["id"] != investor_id:
        raise KeyError(f"unknown fictional investor: {investor_id}")
    return fixture
