from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def setup_function():
    client.post("/api/market/reset")


def test_before_refresh_there_are_no_verdicts_and_trades_are_blocked():
    body = client.get("/api/portfolio/robert").json()
    assert body["refreshed"] is False
    assert all(h["move_pct"] == 0 for h in body["holdings"])
    assert abs(sum(h["weight"] for h in body["holdings"]) - 1.0) < 1e-6
    assert client.get("/api/trade-check/NVDA", params={"action": "sell"}).status_code == 409


def test_positions_have_fictional_shares_cash_and_reprice_on_refresh():
    before = client.get("/api/portfolio/robert").json()
    assert before["cash_cad"] == 10000 and all(h["shares"] > 0 for h in before["holdings"])
    client.post("/api/market/refresh")
    after = client.get("/api/portfolio/robert").json()
    nvda_before = next(h for h in before["holdings"] if h["ticker"] == "NVDA")
    nvda_after = next(h for h in after["holdings"] if h["ticker"] == "NVDA")
    assert nvda_after["shares"] == nvda_before["shares"]  # same shares, new price
    assert nvda_after["price"] < nvda_before["price"]
    assert abs(after["total_value_cad"] - after["invested_cad"] - after["cash_cad"]) < 0.01


def test_demo_accounts_are_seeded_and_portfolios_are_account_linked():
    accounts = client.get("/api/accounts", params={"user_id": "demo", "persona_id": "amira"}).json()
    assert {account["type"] for account in accounts} == {"TFSA", "RRSP", "Non-registered"}
    assert all(account["persona_id"] == "amira" and account["balance"] > 0 for account in accounts)

    non_registered = client.get("/api/portfolio/amira", params={"account_type": "Non-registered"}).json()
    tfsa = client.get("/api/portfolio/amira", params={"account_type": "TFSA"}).json()
    assert non_registered["account_type"] == "Non-registered"
    assert tfsa["account_type"] == "TFSA"
    assert non_registered["total_value_cad"] != tfsa["total_value_cad"]
    assert non_registered["holdings"] and tfsa["holdings"]


def test_refresh_loads_second_dataset():
    status = client.post("/api/market/refresh").json()
    assert status["refreshed"] is True and status["new_price_rows"] == 55 and status["new_headlines"] > 0
    assert client.get("/api/market").json()["refreshed"] is True


def test_holdings_never_show_a_verdict_until_an_action_is_chosen():
    client.post("/api/market/refresh")
    body = client.get("/api/portfolio/amira").json()
    assert all("verdict" not in h for h in body["holdings"])
    assert body["total_value_cad"] < 15000 + body["cash_cad"]
    nvda = client.get("/api/trade-check/NVDA", params={"action": "sell"}).json()
    assert nvda["verdict"] == "panic_risk" and nvda["score"]["value"] < 50


def test_buy_and_sell_checks_use_model_scored_news():
    client.post("/api/market/refresh")
    sell = client.get("/api/trade-check/ENB.TO", params={"action": "sell"}).json()
    buy = client.get("/api/trade-check/GLD", params={"action": "buy"}).json()
    assert sell["verdict"] == "evidence_supported" and sell["computed_by"] == "local-engine"
    assert buy["verdict"] == "chasing_risk" and buy["score"]["name"] == "Hype"
    assert buy["sentiment_label"] == "upbeat"
    sentiment = next(e for e in sell["evidence"] if e["evidence_id"].endswith(":sentiment"))
    assert sentiment["value"] is not None and sentiment["value"] < 0


def test_bad_inputs_are_rejected():
    assert client.get("/api/portfolio/nobody").status_code == 404
    client.post("/api/market/refresh")
    assert client.get("/api/trade-check/NVDA", params={"action": "hold"}).status_code == 422
