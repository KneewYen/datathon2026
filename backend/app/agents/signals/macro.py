"""Macro Signal Agent: rates, yield curve, unemployment from the starter dataset."""
import csv
import os
from pathlib import Path
from typing import Any, Dict, List

DATA_DIR = Path(os.getenv("DATA_DIR", Path(__file__).parents[4] / "data"))


def _series() -> Dict[str, List[tuple]]:
    out: Dict[str, List[tuple]] = {}
    with open(DATA_DIR / "macro_rates.csv", newline="") as f:
        for row in csv.DictReader(f):
            out.setdefault(row["series_id"], []).append((row["date"], float(row["value"])))
    for v in out.values():
        v.sort()
    return out


def recession_signals() -> Dict[str, Any]:
    try:
        s = _series()
    except FileNotFoundError:
        return {"metrics": {}, "sources": [], "warnings": ["macro_rates.csv not found in data/"]}

    us10, us2 = s["DGS10"][-1], s["DGS2"][-1]
    ca10, ca2 = s["BD.CDN.10YR.DQ.YLD"][-1], s["BD.CDN.2YR.DQ.YLD"][-1]
    unrate = s["UNRATE"]
    un_now = unrate[-1]
    un_low_12m = min(v for _, v in unrate[-13:-1])

    us_spread = round(us10[1] - us2[1], 2)
    ca_spread = round(ca10[1] - ca2[1], 2)
    un_change = round(un_now[1] - un_low_12m, 2)

    notes = []
    notes.append(
        f"U.S. yield curve (10y − 2y) is {us_spread:+.2f} pts on {us10[0]}: "
        + ("inverted, a historical warning sign." if us_spread < 0 else "not inverted.")
    )
    notes.append(
        f"Canada yield curve (10y − 2y) is {ca_spread:+.2f} pts on {ca10[0]}: "
        + ("inverted." if ca_spread < 0 else "not inverted.")
    )
    notes.append(
        f"U.S. unemployment is {un_now[1]}% ({un_now[0]}), {un_change:+.2f} pts vs. its 12-month low"
        + (": a sharp rise, often seen near recessions." if un_change >= 0.5 else ": no sharp rise.")
    )
    return {
        "metrics": {
            "US 10y−2y": f"{us_spread:+.2f}",
            "CA 10y−2y": f"{ca_spread:+.2f}",
            "US unemployment": f"{un_now[1]}%",
            "Unemp. vs 12m low": f"{un_change:+.2f}",
        },
        "notes": notes,
        "sources": [
            "FRED: DGS10, DGS2, UNRATE (macro_rates.csv)",
            "Bank of Canada: BD.CDN.10YR.DQ.YLD, BD.CDN.2YR.DQ.YLD (macro_rates.csv)",
        ],
        "warnings": ["Indicators describe the past; they do not predict a recession."],
    }
