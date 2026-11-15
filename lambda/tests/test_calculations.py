from __future__ import annotations

import sys
import unittest
import hashlib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "lambda" / "financial_tools"))

from calculations import (  # noqa: E402
    analyze_holdings_exposure,
    apply_shift,
    compare_strategy_shift,
    market_snapshot,
    simulate_account_purchase,
)
from data_access import _verify_manifest, dataset_from_csv_text  # noqa: E402


STRATEGY_HOLDINGS = {
    "growth": {"QQQ": 0.35, "NVDA": 0.25, "SHOP.TO": 0.20, "SPY": 0.20},
    "dividend": {"XIU.TO": 0.30, "ENB.TO": 0.25, "FTS.TO": 0.25, "PG": 0.20},
    "momentum": {"QQQ": 0.40, "SPY": 0.30, "XIU.TO": 0.30},
    "preservation": {"ZST.TO": 0.40, "XBB.TO": 0.30, "GLD": 0.20, "PG": 0.10},
}


class CalculationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        source = ROOT / "hackathon_info" / "alphaforge_starter"
        cls.dataset = dataset_from_csv_text(
            (source / "prices_daily.csv").read_text(),
            (source / "fx_usdcad_daily.csv").read_text(),
            sources=["fixture:prices", "fixture:fx"],
        )

    def test_shift_moves_percentage_points_without_changing_total(self) -> None:
        proposed = apply_shift(
            {"growth": 0.6, "dividend": 0.2, "momentum": 0.1, "preservation": 0.1},
            "growth",
            "dividend",
            0.2,
        )
        self.assertEqual(proposed["growth"], 0.4)
        self.assertEqual(proposed["dividend"], 0.4)
        self.assertAlmostEqual(sum(proposed.values()), 1.0)

    def test_demo_scenario_matches_golden_risk_results(self) -> None:
        result = compare_strategy_shift(
            {
                "analysis_id": "golden-demo",
                "strategy_allocations": {
                    "growth": 0.6,
                    "dividend": 0.2,
                    "momentum": 0.1,
                    "preservation": 0.1,
                },
                "shift": {
                    "from_strategy": "growth",
                    "to_strategy": "dividend",
                    "amount": 0.2,
                },
                "strategy_holdings": STRATEGY_HOLDINGS,
                "start_date": "2023-11-13",
                "end_date": "2026-11-12",
            },
            self.dataset,
        )
        metrics = {item["evidence_id"]: item for item in result["metrics"]}

        self.assertEqual(result["conclusion"], "risk_reduced")
        self.assertAlmostEqual(
            metrics["metric.annualized_volatility"]["current"], 0.1847614472, places=8
        )
        self.assertAlmostEqual(
            metrics["metric.annualized_volatility"]["proposed"], 0.1370657292, places=8
        )
        self.assertAlmostEqual(
            metrics["metric.maximum_drawdown"]["current"], -0.1972363507, places=8
        )
        self.assertAlmostEqual(
            metrics["metric.maximum_drawdown"]["proposed"], -0.1552909917, places=8
        )
        self.assertLess(
            metrics["metric.annualized_return"]["proposed"],
            metrics["metric.annualized_return"]["current"],
        )
        self.assertEqual(len(result["performance_series"]), 93)

    def test_rejects_duplicate_price_dates(self) -> None:
        prices = (
            "date,ticker,open,high,low,close,adj_close,volume,currency\n"
            "2026-01-02,SPY,1,1,1,1,1,1,USD\n"
            "2026-01-02,SPY,1,1,1,1,1,1,USD\n"
        )
        fx = "date,usdcad,cadusd\n2026-01-02,1.4,0.714286\n"
        with self.assertRaisesRegex(ValueError, "duplicate price dates"):
            dataset_from_csv_text(prices, fx)

    def test_manifest_verifies_dataset_identity_prefix_size_and_checksum(self) -> None:
        body = b"date,ticker\n2026-01-02,SPY\n"
        manifest = {
            "dataset_id": "alphaforge-starter-v1",
            "s3_prefix": "starter/v1",
            "files": [
                {
                    "name": "prices_daily.csv",
                    "bytes": len(body),
                    "sha256": hashlib.sha256(body).hexdigest(),
                }
            ],
        }

        _verify_manifest(
            manifest,
            {"prices_daily.csv": body},
            "alphaforge-starter-v1",
            "starter/v1",
        )

    def test_manifest_rejects_changed_s3_object(self) -> None:
        original = b"reviewed"
        manifest = {
            "dataset_id": "alphaforge-starter-v1",
            "s3_prefix": "starter/v1",
            "files": [
                {
                    "name": "prices_daily.csv",
                    "bytes": len(original),
                    "sha256": hashlib.sha256(original).hexdigest(),
                }
            ],
        }

        with self.assertRaisesRegex(ValueError, "checksum does not match"):
            _verify_manifest(
                manifest,
                {"prices_daily.csv": b"tampered"},
                "alphaforge-starter-v1",
                "starter/v1",
            )

    def test_investment_tools_measure_exposure_market_and_purchase_risk(self) -> None:
        event = {
            "analysis_id": "investment-test",
            "target_ticker": "NVDA",
            "amount": 2000,
            "currency": "CAD",
            "account_id": "tfsa-test",
            "start_date": "2023-11-13",
            "end_date": "2026-11-12",
            "accounts": [
                {
                    "id": "tfsa-test",
                    "name": "Fictional TFSA",
                    "type": "TFSA",
                    "risk_tolerance": "aggressive",
                    "objective": "Long-term growth",
                    "cash_cad": 5000,
                    "holdings": [
                        {"ticker": "NVDA", "quantity": 2},
                        {"ticker": "QQQ", "quantity": 4},
                    ],
                    "risk_constraints": {
                        "max_single_company_exposure": 0.5,
                        "minimum_cash_cad": 500,
                    },
                }
            ],
            "etf_constituents": {
                "fixture_version": "test-etf-v1",
                "retrieved_at": "2026-11-12T00:00:00Z",
                "holdings": [
                    {
                        "etf_ticker": "QQQ",
                        "constituent_ticker": "NVDA",
                        "weight": 0.08,
                        "as_of": "2026-11-12",
                        "url": "https://example.test/issuer",
                    }
                ],
            },
        }

        exposure = analyze_holdings_exposure(event, self.dataset)
        market = market_snapshot(event, self.dataset)
        simulation = simulate_account_purchase(event, self.dataset)

        self.assertGreater(exposure["portfolio"]["direct_value_cad"], 0)
        self.assertGreater(exposure["portfolio"]["indirect_value_cad"], 0)
        self.assertEqual(market["metrics"]["price_as_of"], "2026-11-12")
        self.assertGreater(simulation["option"]["shares_purchasable"], 0)
        self.assertEqual(simulation["option"]["remaining_cash_cad"], 3000)
        self.assertGreater(
            simulation["option"]["proposed_nvda_exposure"],
            simulation["option"]["current_nvda_exposure"],
        )
        self.assertGreater(
            simulation["option"]["proposed_target_risk_contribution"],
            simulation["option"]["current_target_risk_contribution"],
        )
        self.assertGreaterEqual(simulation["option"]["proposed_target_correlation"], -1)
        self.assertLessEqual(simulation["option"]["proposed_target_correlation"], 1)

    def test_market_snapshot_converts_usd_close_and_rejects_missing_ticker(self) -> None:
        event = {
            "analysis_id": "market-test",
            "target_ticker": "NVDA",
            "start_date": "2023-11-13",
            "end_date": "2026-11-12",
        }
        result = market_snapshot(event, self.dataset)
        latest = self.dataset.prices["NVDA"][-1]
        expected = latest.close_price * self.dataset.prior_usdcad(latest.observation_date)
        self.assertAlmostEqual(result["metrics"]["price_cad"], expected, places=8)

        with self.assertRaisesRegex(ValueError, "no market price"):
            market_snapshot({**event, "target_ticker": "MISSING"}, self.dataset)


if __name__ == "__main__":
    unittest.main()
