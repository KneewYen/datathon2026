#!/usr/bin/env python3
"""Score headlines with Amazon Bedrock (sentiment + scope + category).

Reads  data/simulated/{current,marketchange}/news.csv   (default)
       data/real/news.csv                               (--source real, from fetch_news.py)
Writes the matching news_scored.csv next to it.

For every headline each model returns:
  sentiment  -1.0 (very negative) .. +1.0 (very positive) for an investor holding the ticker
  scope      "company" if the news is about that company's own business or events,
             "market" if it is about the market, a sector or the economy
  category   earnings, dividend, regulatory, legal, credit_rating, analyst, leadership,
             competitor, operations, market or other

Multi-model voting: set BEDROCK_VOTE_MODEL_IDS="id1,id2,id3" to score with several models.
The sentiment is the median of the votes, scope and category are majority votes, and the
spread between models is saved so disputed headlines can be reviewed. With one model
(BEDROCK_MODEL_ID) the output matches the earlier format plus the new columns.

The hand-written ``scope`` from the generator is kept as ``label_scope`` so the
model's judgement can be compared with it. Scores are precomputed here, never at
request time, and temperature 0 keeps reruns stable. Run with the backend venv:

    backend/.venv/bin/python scripts/score_news_sentiment.py
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import re
import sys
from pathlib import Path

import boto3
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "lambda" / "financial_tools"))

import sentiment_tools  # noqa: E402

SIM = ROOT / "data" / "simulated"
REAL = ROOT / "data" / "real"
UNIVERSE = ROOT / "hackathon_info" / "alphaforge_starter" / "assets_universe.csv"

SYSTEM = """You classify short financial news headlines for an investor who holds one ticker.
Return JSON only: {"sentiment": <number from -1.0 to 1.0>, "scope": "company" or "market", "category": <one of CATEGORIES>}.
sentiment: how good or bad the headline is for holders of that ticker (-1 very bad, 0 neutral, 1 very good).
scope: "company" if the headline is about that specific company's own business, regulators, ratings or
operations; "market" if it is about the broader market, a sector, rates, the economy or investor mood.
category: the main topic. One of: """ + ", ".join(sentiment_tools.CATEGORIES) + """.
Use "market" for market-wide, sector or macro news. Judge only the headline. No explanation."""


def names() -> dict[str, str]:
    with UNIVERSE.open(newline="") as handle:
        return {r["ticker"]: r["name"] for r in csv.DictReader(handle)}


def parse(text: str) -> tuple[float, str, str]:
    match = re.search(r"\{.*\}", text, re.S)
    if not match:
        raise ValueError(f"no JSON in model output: {text!r}")
    value = json.loads(match.group(0))
    sentiment = float(value["sentiment"])
    scope = value["scope"]
    category = value.get("category", "other")
    if not -1.0 <= sentiment <= 1.0 or scope not in ("company", "market"):
        raise ValueError(f"out-of-range model output: {value}")
    if category not in sentiment_tools.CATEGORIES:
        category = "other"
    return round(sentiment, 2), scope, category


def score_headline(client, model_ids: list[str], prompt: str) -> dict:
    """Ask every model, then combine: median sentiment, majority scope and category."""
    votes = []
    for model_id in model_ids:
        response = client.converse(
            modelId=model_id,
            system=[{"text": SYSTEM}],
            messages=[{"role": "user", "content": [{"text": prompt}]}],
            inferenceConfig={"temperature": 0, "maxTokens": 80},
        )
        votes.append(parse(response["output"]["message"]["content"][0]["text"]))
    combined = sentiment_tools.aggregate_votes([v[0] for v in votes])
    return {
        "sentiment": combined["sentiment"],
        "scope": sentiment_tools.majority_label([v[1] for v in votes]),
        "category": sentiment_tools.majority_label([v[2] for v in votes]),
        "spread": combined["spread"],
        "agreement": combined["agreement"],
        "votes": combined["votes"],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", choices=("simulated", "real"), default="simulated")
    args = parser.parse_args()
    load_dotenv(ROOT / "backend" / ".env")
    vote_ids = os.environ.get("BEDROCK_VOTE_MODEL_IDS", "")
    model_ids = [m.strip() for m in vote_ids.split(",") if m.strip()] or [os.environ["BEDROCK_MODEL_ID"]]
    client = boto3.client("bedrock-runtime", region_name=os.environ["AWS_REGION"])
    company = names()
    agree = total = 0
    folders = [SIM / "current", SIM / "marketchange"] if args.source == "simulated" else [REAL]
    for folder in folders:
        with (folder / "news.csv").open(newline="") as handle:
            rows = list(csv.DictReader(handle))
        out = []
        for row in rows:
            prompt = f"Ticker: {row['ticker']} ({company.get(row['ticker'], row['ticker'])})\nHeadline: {row['headline']}"
            result = score_headline(client, model_ids, prompt)
            total += 1
            agree += result["scope"] == row["scope"]
            out.append(
                {
                    "date": row["date"],
                    "ticker": row["ticker"],
                    "headline": row["headline"],
                    "scope": result["scope"],
                    "label_scope": row["scope"],
                    "category": result["category"],
                    "sentiment": result["sentiment"],
                    "model_spread": result["spread"],
                    "model_agreement": result["agreement"],
                    "model_id": "+".join(model_ids),
                    "source": row["source"],
                }
            )
            flag = "" if result["agreement"] else "  <-- models disagree"
            print(f"{row['ticker']:8} {result['sentiment']:+.2f} {result['scope']:8} {result['category']:13} {row['headline'][:50]}{flag}")
        with (folder / "news_scored.csv").open("w", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(out[0]))
            writer.writeheader()
            writer.writerows(out)
    print(f"\nmodel scope agrees with the hand label on {agree}/{total} headlines")


if __name__ == "__main__":
    sys.exit(main())
