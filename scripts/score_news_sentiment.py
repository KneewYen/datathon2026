#!/usr/bin/env python3
"""Score the simulated headlines with Amazon Bedrock (sentiment + scope).

Reads  data/simulated/{current,marketchange}/news.csv
Writes data/simulated/{current,marketchange}/news_scored.csv

For every headline the model returns:
  sentiment  -1.0 (very negative) .. +1.0 (very positive) for an investor holding the ticker
  scope      "company" if the news is about that company's own business or events,
             "market" if it is about the market, a sector or the economy

The hand-written ``scope`` from the generator is kept as ``label_scope`` so the
model's judgement can be compared with it. Scores are precomputed here, never at
request time, and temperature 0 keeps reruns stable. Run with the backend venv:

    backend/.venv/bin/python scripts/score_news_sentiment.py
"""
from __future__ import annotations

import csv
import json
import os
import re
import sys
from pathlib import Path

import boto3
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
SIM = ROOT / "data" / "simulated"
UNIVERSE = ROOT / "hackathon_info" / "alphaforge_starter" / "assets_universe.csv"

SYSTEM = """You classify short financial news headlines for an investor who holds one ticker.
Return JSON only: {"sentiment": <number from -1.0 to 1.0>, "scope": "company" or "market"}.
sentiment: how good or bad the headline is for holders of that ticker (-1 very bad, 0 neutral, 1 very good).
scope: "company" if the headline is about that specific company's own business, regulators, ratings or
operations; "market" if it is about the broader market, a sector, rates, the economy or investor mood.
Judge only the headline. No explanation."""


def names() -> dict[str, str]:
    with UNIVERSE.open(newline="") as handle:
        return {r["ticker"]: r["name"] for r in csv.DictReader(handle)}


def parse(text: str) -> tuple[float, str]:
    match = re.search(r"\{.*\}", text, re.S)
    if not match:
        raise ValueError(f"no JSON in model output: {text!r}")
    value = json.loads(match.group(0))
    sentiment = float(value["sentiment"])
    scope = value["scope"]
    if not -1.0 <= sentiment <= 1.0 or scope not in ("company", "market"):
        raise ValueError(f"out-of-range model output: {value}")
    return round(sentiment, 2), scope


def main() -> None:
    load_dotenv(ROOT / "backend" / ".env")
    model_id = os.environ["BEDROCK_MODEL_ID"]
    client = boto3.client("bedrock-runtime", region_name=os.environ["AWS_REGION"])
    company = names()
    agree = total = 0
    for folder in ("current", "marketchange"):
        with (SIM / folder / "news.csv").open(newline="") as handle:
            rows = list(csv.DictReader(handle))
        out = []
        for row in rows:
            prompt = f"Ticker: {row['ticker']} ({company.get(row['ticker'], row['ticker'])})\nHeadline: {row['headline']}"
            response = client.converse(
                modelId=model_id,
                system=[{"text": SYSTEM}],
                messages=[{"role": "user", "content": [{"text": prompt}]}],
                inferenceConfig={"temperature": 0, "maxTokens": 60},
            )
            sentiment, scope = parse(response["output"]["message"]["content"][0]["text"])
            total += 1
            agree += scope == row["scope"]
            out.append(
                {
                    "date": row["date"],
                    "ticker": row["ticker"],
                    "headline": row["headline"],
                    "scope": scope,
                    "label_scope": row["scope"],
                    "sentiment": sentiment,
                    "model_id": model_id,
                    "source": row["source"],
                }
            )
            print(f"{row['ticker']:8} {sentiment:+.2f} {scope:8} (label {row['scope']:8}) {row['headline'][:60]}")
        with (SIM / folder / "news_scored.csv").open("w", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(out[0]))
            writer.writeheader()
            writer.writerows(out)
    print(f"\nmodel scope agrees with the hand label on {agree}/{total} headlines")


if __name__ == "__main__":
    sys.exit(main())
