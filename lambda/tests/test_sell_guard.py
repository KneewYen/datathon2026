"""Tests for the deterministic sell guard, using the two simulated datasets."""
from __future__ import annotations

import csv
import json
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "lambda" / "financial_tools"))

from sell_guard import decide, evaluate_sell, evaluate_trade, score_signals  # noqa: E402

SIM = ROOT / "data" / "simulated"


def rows(path: Path) -> list[dict]:
    with path.open(newline="") as handle:
        return list(csv.DictReader(handle))


class SellGuardTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.current = rows(SIM / "current" / "prices.csv")
        cls.change = rows(SIM / "marketchange" / "prices.csv")
        cls.news = rows(SIM / "current" / "news_scored.csv") + rows(SIM / "marketchange" / "news_scored.csv")
        meta = json.loads((SIM / "marketchange" / "dataset.json").read_text())
        cls.expected = meta["expected_verdict_if_sold"]
        cls.expected_buy = meta["expected_verdict_if_bought"]

    def verdict(self, ticker: str, as_of: str) -> str:
        return evaluate_sell(ticker, self.current, self.change, self.news, as_of)["verdict"]

    def test_every_ticker_matches_expected_verdict_on_day_one_and_last_day(self) -> None:
        for as_of in ("2026-11-13", "2026-11-19"):
            for ticker, expected in self.expected.items():
                with self.subTest(ticker=ticker, as_of=as_of):
                    self.assertEqual(self.verdict(ticker, as_of), expected)

    def test_buy_verdicts_match_expected_on_last_day(self) -> None:
        for ticker, expected in self.expected_buy.items():
            with self.subTest(ticker=ticker):
                result = evaluate_trade("buy", ticker, self.current, self.change, self.news, "2026-11-19")
                self.assertEqual(result["verdict"], expected)

    def test_model_sentiment_is_used_as_evidence(self) -> None:
        result = evaluate_sell("ENB.TO", self.current, self.change, self.news, "2026-11-19")
        sentiment = next(i for i in result["evidence"] if i["evidence_id"] == "ENB.TO:sentiment")
        self.assertLess(sentiment["value"], -0.3)

    def test_result_is_deterministic(self) -> None:
        first = evaluate_sell("NVDA", self.current, self.change, self.news, "2026-11-13")
        second = evaluate_sell("NVDA", self.current, self.change, self.news, "2026-11-13")
        self.assertEqual(first, second)

    def test_evidence_is_labelled_and_versioned(self) -> None:
        result = evaluate_sell("ENB.TO", self.current, self.change, self.news, "2026-11-13")
        ids = {item["evidence_id"] for item in result["evidence"]}
        self.assertIn("ENB.TO:drop", ids)
        self.assertTrue(all(i["formula_version"] == "trade-guard-v3" for i in result["evidence"]))
        sentiment = next(i for i in result["evidence"] if i["evidence_id"] == "ENB.TO:sentiment")
        self.assertIsNotNone(sentiment["value"])  # headlines are model-scored

    def test_only_data_up_to_as_of_is_used(self) -> None:
        early = evaluate_sell("ENB.TO", self.current, self.change, self.news, "2026-11-13")
        late = evaluate_sell("ENB.TO", self.current, self.change, self.news, "2026-11-19")
        drop = lambda r: next(i for i in r["evidence"] if i["evidence_id"].endswith(":drop"))["value"]
        self.assertGreater(drop(early), drop(late))  # the drop keeps deepening

    def test_unknown_ticker_or_date_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            evaluate_sell("NVDA", self.current, self.change, self.news, "2026-11-01")

    def test_scores_stay_between_zero_and_one(self) -> None:
        for sentiment in (None, -1.0, 0.0, 1.0):
            scores = score_signals(10.0, 9.0, 20.0, 1.0, 1.0, sentiment)
            self.assertTrue(all(0.0 <= value <= 1.0 for value in scores.values()), scores)

    def test_missing_sentiment_is_neutral_not_invented(self) -> None:
        none = score_signals(0.0, 3.0, 0.0, 0.5, 0.3, None)
        zero = score_signals(0.0, 3.0, 0.0, 0.5, 0.3, 0.0)
        self.assertEqual(none, zero)

    def test_negative_sentiment_raises_fundamental_and_upbeat_raises_hype(self) -> None:
        base = score_signals(2.0, 3.0, 0.0, 0.5, 0.3, 0.0)
        bad = score_signals(2.0, 3.0, 0.0, 0.5, 0.3, -0.9)
        good = score_signals(2.0, 3.0, 0.0, 0.5, 0.3, 0.9)
        self.assertGreater(bad["fundamental"], base["fundamental"])
        self.assertGreater(good["hype"], base["hype"])

    def test_decide_rules(self) -> None:
        company = {"fundamental": 0.9, "emotion": 0.4, "hype": 0.1}
        market = {"fundamental": 0.3, "emotion": 0.8, "hype": 0.1}
        even = {"fundamental": 0.5, "emotion": 0.5, "hype": 0.1}
        hype = {"fundamental": 0.1, "emotion": 0.2, "hype": 0.7}
        self.assertEqual(decide("sell", -2.0, 0.0, 3.0, company)["verdict"], "no_signal")  # small move
        self.assertEqual(decide("sell", -8.0, 0.0, 1.0, company)["verdict"], "no_signal")  # normal volume
        self.assertEqual(decide("sell", -8.0, 0.0, 3.0, company)["verdict"], "evidence_supported")
        self.assertEqual(decide("sell", -8.0, 0.0, 3.0, market)["verdict"], "panic_risk")
        self.assertEqual(decide("sell", -8.0, 0.0, 3.0, even)["verdict"], "mixed")
        self.assertEqual(decide("buy", -8.0, 0.0, 3.0, company)["verdict"], "falling_knife")
        self.assertEqual(decide("buy", -8.0, 0.0, 3.0, market)["verdict"], "dip_with_context")
        self.assertEqual(decide("buy", -1.0, 5.0, 3.0, hype)["verdict"], "chasing_risk")
        self.assertEqual(decide("sell", -1.0, 5.0, 3.0, hype)["verdict"], "no_signal")  # nothing to panic about

    def test_result_reports_score_and_sentiment(self) -> None:
        sell = evaluate_trade("sell", "NVDA", self.current, self.change, self.news, "2026-11-13")
        self.assertEqual(sell["verdict"], "panic_risk")
        self.assertLess(sell["score"]["value"], 50)
        self.assertEqual(sell["sentiment_label"], "negative")
        buy = evaluate_trade("buy", "GLD", self.current, self.change, self.news, "2026-11-19")
        self.assertEqual(buy["score"]["name"], "Hype")
        self.assertEqual(buy["sentiment_label"], "upbeat")


if __name__ == "__main__":
    unittest.main()
