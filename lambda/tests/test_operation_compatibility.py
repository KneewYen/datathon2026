from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "lambda" / "financial_tools"))

import handler as lambda_handler  # noqa: E402
import backtest  # noqa: E402
import market_store  # noqa: E402
import market_tools  # noqa: E402
import ops  # noqa: E402
import sell_guard  # noqa: E402


MARKET_DATA = {
    "current": [
        {"date": "2026-01-01", "ticker": "NVDA", "close": "100", "volume": "100"},
        {"date": "2026-01-01", "ticker": "SPY", "close": "100", "volume": "100"},
    ],
    "change": [
        {"date": "2026-01-02", "ticker": "NVDA", "close": "90", "volume": "400"},
        {"date": "2026-01-02", "ticker": "SPY", "close": "95", "volume": "300"},
    ],
    "news": [
        {
            "date": "2026-01-02",
            "ticker": "NVDA",
            "headline": "Sector demand changes",
            "scope": "market",
            "category": "market",
            "sentiment": "-0.2",
        }
    ],
    "dates": ["2026-01-02"],
    "universe": [
        {"ticker": "NVDA", "name": "NVIDIA", "sector": "Technology"},
        {"ticker": "SPY", "name": "S&P 500 ETF", "sector": "Technology"},
    ],
    "names": {"NVDA": "NVIDIA", "SPY": "S&P 500 ETF"},
    "peers": {"NVDA": ["SPY"], "SPY": ["NVDA"]},
    "sources": ["fixture:simulated-market-v1"],
}


class MemoryStore:
    kind = "local"
    label = "memory://market"

    def __init__(self) -> None:
        self.writes: dict[str, bytes] = {}

    def read(self, name: str):
        if name.endswith("news.csv"):
            return (
                b"date,ticker,headline,scope,source\n"
                b"2026-01-02,NVDA,Sector demand changes,market,fixture\n",
                f"memory://{name}",
            )
        raise RuntimeError(f"unsupported fixture read: {name}")

    def write(self, name: str, body: bytes):
        self.writes[name] = body
        return f"memory://{name}"


class FakeBedrock:
    def converse(self, **_kwargs):
        return {
            "output": {
                "message": {
                    "content": [
                        {
                            "text": json.dumps(
                                {
                                    "sentiment": -0.2,
                                    "scope": "market",
                                    "category": "market",
                                }
                            )
                        }
                    ]
                }
            }
        }


class OperationCompatibilityTests(unittest.TestCase):
    def test_deployed_market_operation_contracts_remain_available(self) -> None:
        stores = SimpleNamespace()
        with patch.object(market_store, "load_market", return_value=MARKET_DATA):
            status = ops.run({"operation": "market_status", "live": True}, stores)
            sentiment = ops.run(
                {"operation": "sentiment_summary", "ticker": "NVDA", "live": True},
                stores,
            )
            trade = ops.run(
                {
                    "operation": "trade_check",
                    "ticker": "NVDA",
                    "action": "sell",
                    "live": True,
                },
                stores,
            )

        self.assertEqual(set(ops.MARKET_OPERATIONS), {
            "market_status",
            "portfolio_snapshot",
            "trade_check",
            "sentiment_summary",
            "score_headlines",
            "market_agent",
            "classifier_agent",
            "investor_position",
            "account_values",
        })
        self.assertEqual(status["new_price_rows"], 2)
        self.assertEqual(sentiment["ticker"], "NVDA")
        self.assertIn(trade["trade_check"]["verdict"], {
            "evidence_supported",
            "panic_risk",
            "mixed",
            "no_signal",
        })

    def test_deployed_split_market_and_classifier_agents_remain_available(self) -> None:
        stores = SimpleNamespace()
        with patch.object(market_store, "load_market", return_value=MARKET_DATA):
            market = ops.run(
                {
                    "operation": "market_agent",
                    "ticker": "NVDA",
                    "live": True,
                },
                stores,
            )
            classified = ops.run(
                {
                    "operation": "classifier_agent",
                    "action": "sell",
                    "market": market["market"],
                },
                stores,
            )
            position = ops.run(
                {
                    "operation": "investor_position",
                    "persona_id": "amira",
                    "persona": {
                        "starting_balance_cad": 100_000,
                        "starting_cash_cad": 10_000,
                        "default_allocations": {"growth": 1.0},
                    },
                    "strategy_holdings": {"growth": {"NVDA": 1.0}},
                    "ticker": "NVDA",
                    "action": "sell",
                    "live": True,
                },
                stores,
            )

        self.assertEqual(market["market"]["ticker"], "NVDA")
        self.assertIn(classified["trade_check"]["driver"], {"company", "market", "mixed"})
        self.assertTrue(classified["trade_check"]["evidence"])
        self.assertTrue(position["position"]["holds"])
        self.assertEqual(position["position"]["ticker"], "NVDA")

    def test_account_values_preserves_cash_aware_deployed_contract(self) -> None:
        stores = SimpleNamespace()
        event = {
            "operation": "account_values",
            "persona_id": "amira",
            "persona": {
                "starting_balance_cad": 100_000,
                "starting_cash_cad": 10_000,
                "default_allocations": {"growth": 1.0},
            },
            "strategy_holdings": {"growth": {"NVDA": 1.0}},
            "live": False,
            "accounts": [
                {
                    "account_type": "TFSA",
                    "account": {
                        "share": 0.5,
                        "cash_share": 0.2,
                        "allocations": {"growth": 1.0},
                    },
                }
            ],
        }

        with patch.object(market_store, "load_market", return_value=MARKET_DATA):
            result = ops.run(event, stores)

        tfsa = result["values"]["TFSA"]
        self.assertEqual(result["operation"], "account_values")
        self.assertEqual(tfsa["starting_balance_cad"], 50_000)
        self.assertEqual(tfsa["invested_cad"], 40_000)
        self.assertEqual(tfsa["cash_cad"], 10_000)
        self.assertEqual(tfsa["value_cad"], 50_000)
        self.assertEqual(tfsa["invested_cad"] + tfsa["cash_cad"], tfsa["value_cad"])

    def test_portfolio_snapshot_does_not_double_count_cash(self) -> None:
        snapshot = market_tools.portfolio_snapshot(
            MARKET_DATA,
            {
                "persona_id": "amira",
                "persona": {
                    "starting_balance_cad": 100_000,
                    "starting_cash_cad": 10_000,
                    "default_allocations": {"growth": 1.0},
                },
                "strategy_holdings": {"growth": {"NVDA": 1.0}},
                "account_type": "TFSA",
                "account": {
                    "share": 0.5,
                    "cash_share": 0.2,
                    "allocations": {"growth": 1.0},
                },
                "live": False,
            },
        )

        self.assertEqual(snapshot["starting_balance_cad"], 50_000)
        self.assertEqual(snapshot["invested_cad"], 40_000)
        self.assertEqual(snapshot["cash_cad"], 10_000)
        self.assertEqual(snapshot["total_value_cad"], 50_000)
        self.assertNotEqual(snapshot["total_value_cad"], 60_000)

    def test_classifier_forwards_risk_band_and_growth_style(self) -> None:
        market = sell_guard.market_change(
            "NVDA",
            MARKET_DATA["current"],
            MARKET_DATA["change"],
            "2026-01-02",
        )
        expected = {"status": "ok", "verdict": "no_signal", "evidence": []}
        with patch.object(
            market_tools.sell_guard,
            "classify_move",
            return_value=expected,
        ) as classify:
            result = market_tools.classifier_agent(
                MARKET_DATA,
                {
                    "action": "sell",
                    "market": market,
                    "risk_band": "low",
                    "growth_style": True,
                },
            )

        self.assertIs(result["trade_check"], expected)
        self.assertEqual(classify.call_args.kwargs["risk_band"], "low")
        self.assertIs(classify.call_args.kwargs["growth_style"], True)

    def test_sell_guard_preserves_profile_thresholds_and_adjustments(self) -> None:
        market = sell_guard.market_change(
            "NVDA",
            MARKET_DATA["current"],
            MARKET_DATA["change"],
            "2026-01-02",
        )
        result = sell_guard.classify_move(
            "sell",
            market,
            MARKET_DATA["news"],
            peers=MARKET_DATA["peers"],
            risk_band="low",
            growth_style=True,
        )

        self.assertEqual(result["risk_band"], "low")
        self.assertEqual(result["thresholds"], sell_guard.RISK_BAND_THRESHOLDS["low"])
        self.assertEqual(result["profile_adjustment"]["net_bias"], 0.4)
        self.assertEqual(result["profile_adjustment"]["style_bias"], 0.3)
        self.assertIs(result["profile_adjustment"]["growth_style"], True)

    def test_backtest_module_preserves_supported_result_contract(self) -> None:
        change = [
            *MARKET_DATA["change"],
            {"date": "2026-01-03", "ticker": "NVDA", "close": "94", "volume": "250"},
            {"date": "2026-01-03", "ticker": "SPY", "close": "97", "volume": "220"},
        ]

        result = backtest.backtest(
            MARKET_DATA["current"],
            change,
            MARKET_DATA["news"],
            peers=MARKET_DATA["peers"],
        )

        self.assertEqual(result["last_day"], "2026-01-03")
        self.assertGreater(result["evaluations"], 0)
        self.assertEqual(result["evaluations"], len(result["rows"]))
        self.assertEqual(result["scored"] + result["unscored"], result["evaluations"])

    def test_headline_scoring_keeps_bounded_folders_and_writes(self) -> None:
        store = MemoryStore()
        stores = market_store.MarketStores(market=store, reference=store)
        with patch.object(market_store, "load_market", return_value={"names": {"NVDA": "NVIDIA"}}):
            result = ops.run(
                {
                    "operation": "score_headlines",
                    "model_ids": ["us.amazon.nova-lite-v1:0"],
                },
                stores,
                bedrock_client=FakeBedrock(),
            )

        self.assertEqual(result["status"], "ok")
        self.assertEqual(
            set(store.writes),
            {"current/news_scored.csv", "marketchange/news_scored.csv"},
        )
        self.assertTrue(all(body.startswith(b"date,ticker,headline") for body in store.writes.values()))

    def test_lambda_dispatch_preserves_legacy_shape_and_adds_new_trace_only_when_requested(self) -> None:
        context = SimpleNamespace(aws_request_id="request-test")
        with (
            patch.object(lambda_handler.market_store, "stores_from_env", return_value=SimpleNamespace()),
            patch.object(
                lambda_handler.ops,
                "run",
                return_value={"status": "ok", "operation": "market_status", "refreshed": True},
            ),
        ):
            legacy = lambda_handler.handler({"operation": "market_status", "live": True}, context)

        self.assertEqual(legacy["aws_request_id"], "request-test")
        self.assertNotIn("execution_event", legacy)

        with (
            patch.object(lambda_handler, "load_dataset_from_s3", return_value=object()),
            patch.object(
                lambda_handler,
                "market_snapshot",
                return_value={"status": "ok", "operation": "market_snapshot", "evidence": []},
            ),
        ):
            investment = lambda_handler.handler(
                {
                    "operation": "market_snapshot",
                    "analysis_id": "analysis-test",
                    "parent_event_id": "agent.momentum_strategy_agent",
                },
                context,
            )

        self.assertEqual(investment["execution_event"]["parent_id"], "agent.momentum_strategy_agent")
        self.assertEqual(investment["execution_event"]["request_id"], "analysis-test")

    def test_routed_tool_authorization_is_enforced_at_financial_lambda_runtime(self) -> None:
        context = SimpleNamespace(aws_request_id="request-test")
        with (
            patch.object(lambda_handler, "load_dataset_from_s3", return_value=object()),
            patch.object(
                lambda_handler,
                "market_snapshot",
                return_value={"status": "ok", "operation": "market_snapshot", "evidence": []},
            ) as calculation,
        ):
            allowed = lambda_handler.handler(
                {
                    "operation": "market_snapshot",
                    "agent": "momentum_strategy_agent",
                    "routing_authorization": {
                        "agent": "momentum_strategy_agent",
                        "operation": "market_snapshot",
                        "delegation_id": "delegation.tfsa.momentum.market",
                    },
                },
                context,
            )
            denied = lambda_handler.handler(
                {
                    "operation": "market_snapshot",
                    "agent": "growth_strategy_agent",
                    "routing_authorization": {
                        "agent": "growth_strategy_agent",
                        "operation": "market_snapshot",
                        "delegation_id": "delegation.tfsa.growth.market",
                    },
                },
                context,
            )

        self.assertEqual(allowed["status"], "ok")
        self.assertEqual(denied["status"], "error")
        self.assertIn("not authorized", denied["error"])
        self.assertEqual(calculation.call_count, 1)


if __name__ == "__main__":
    unittest.main()
