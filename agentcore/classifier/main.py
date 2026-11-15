"""Classifier agent (AgentCore runtime): market-driven or company-driven, with a sentiment label.

Tool: ``classify_move``. Deterministic code in the financial-tools AWS Lambda scores the Market
agent's change and the headlines (their sentiment pre-scored by Bedrock) into fundamental, emotion
and hype scores and a verdict. The investor's risk band and whether the ticker is a growth holding
change how big a move must be and how a sell is judged: Robert selling NVDA is not a panic sell.
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from bedrock_agentcore.runtime import BedrockAgentCoreApp  # noqa: E402

from common import envelope, run_agent  # noqa: E402

app = BedrockAgentCoreApp()

SYSTEM = """You are the Classifier agent of PortfolioGuard AI. Call classify_move exactly once, then reply with the
single word done. Never change the verdict or any score; the tool is the source of truth."""


def work(p: dict) -> dict:
    from app.agents import persona_fit
    from app.services import sell_guard_service

    action, ticker = p["action"], str(p["ticker"]).strip().upper()
    captured: dict = {}

    def classify_move() -> dict:
        """Label the move and score it from the Market agent's output (AWS Lambda; no model decides)."""
        captured["classified"] = sell_guard_service.classifier_agent(
            action, p["market"], p.get("risk_band"), persona_fit.is_growth_style(ticker)
        )
        return captured["classified"]

    return run_agent("classifier", SYSTEM, [classify_move], f"Classify the {action} of {ticker}.", captured, "classified")


@app.entrypoint
def invoke(payload, context=None):
    return envelope(lambda: work((payload or {}).get("payload") or payload or {}))


if __name__ == "__main__":
    app.run()
