"""Market agent (AgentCore runtime): what changed between the two market snapshots.

Tool: ``compare_snapshots``. It invokes the financial-tools AWS Lambda, which reads the versioned
market data from S3 (before the trade, and after the refresh) and reports the price move, volume
and how many tracked tickers fell together, with citable evidence IDs.
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from bedrock_agentcore.runtime import BedrockAgentCoreApp  # noqa: E402

from common import envelope, run_agent  # noqa: E402

app = BedrockAgentCoreApp()

SYSTEM = """You are the Market agent of PortfolioGuard AI. Call compare_snapshots exactly once, then reply with the
single word done. Never state or alter any figure; the tool is the source of truth."""


def work(p: dict) -> dict:
    from app.services import sell_guard_service

    ticker = str(p["ticker"]).strip().upper()
    captured: dict = {}

    def compare_snapshots() -> dict:
        """Compare the market before and after the refresh for the ticker (AWS Lambda over S3)."""
        captured["market"] = sell_guard_service.market_agent(ticker, bool(p.get("live")))
        return captured["market"]

    return run_agent("market", SYSTEM, [compare_snapshots], f"Compare the snapshots for {ticker}.", captured, "market")


@app.entrypoint
def invoke(payload, context=None):
    return envelope(lambda: work((payload or {}).get("payload") or payload or {}))


if __name__ == "__main__":
    app.run()
