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


def test_chat_sell_question_before_refresh_asks_to_load_the_market():
    body = client.post("/api/chat", json={"message": "Should I sell Nvidia?"}).json()
    assert body["trade_check"] is None
    assert "refresh" in body["answer"].lower()


def test_chat_sell_and_buy_questions_return_the_live_trade_check():
    client.post("/api/market/refresh")
    sell = client.post("/api/chat", json={"message": "should I sell nvidia"}).json()["trade_check"]
    buy = client.post("/api/chat", json={"message": "Should I buy NVDA?"}).json()["trade_check"]
    assert sell["ticker"] == buy["ticker"] == "NVDA"
    assert (sell["action"], buy["action"]) == ("sell", "buy")
    assert sell["verdict"] == "panic_risk" and buy["verdict"] == "dip_with_context"
    assert any(e["evidence_id"] == "NVDA:peer_sentiment" for e in sell["evidence"])


def test_chat_trade_question_works_in_french_and_for_other_names():
    client.post("/api/market/refresh")
    body = client.post("/api/chat", json={"message": "Devrais-je vendre Enbridge ?", "lang": "fr"}).json()
    assert body["trade_check"]["ticker"] == "ENB.TO" and body["trade_check"]["verdict"] == "evidence_supported"
    assert "Voici" in body["answer"]


def test_chat_stock_without_market_data_is_explained_not_crashed():
    client.post("/api/market/refresh")
    body = client.post("/api/chat", json={"message": "Should I buy Apple?"}).json()
    assert body["trade_check"] is None and "AAPL" in body["answer"]


def test_chat_without_buy_or_sell_is_not_a_trade_question():
    body = client.post("/api/chat", json={"message": "Tell me about Nvidia"}).json()
    assert body["trade_check"] is None


def test_chat_trade_answer_includes_the_investors_position():
    client.post("/api/market/refresh")
    body = client.post(
        "/api/chat", json={"message": "should I sell gold", "holdings_persona": "robert"}
    ).json()
    assert body["trade_check"]["ticker"] == "GLD"
    pos = body["position"]
    assert pos["holds"] and pos["shares_held"] > 0 and pos["sample_qty"] >= 1
    assert pos["sample_amount_cad"] == round(pos["sample_qty"] * pos["price"], 2)
    assert 0 < pos["portfolio_pct"] < 100


def test_chat_position_for_a_stock_the_investor_does_not_hold():
    client.post("/api/market/refresh")
    body = client.post("/api/chat", json={"message": "should I sell qqq", "holdings_persona": "robert"}).json()
    held = {h["ticker"] for h in client.get("/api/portfolio/robert").json()["holdings"]}
    assert body["position"]["holds"] == ("QQQ" in held)


def test_chat_without_persona_has_no_position_and_synonyms_resolve():
    client.post("/api/market/refresh")
    for text, ticker in (("should i sell nasdaq", "QQQ"), ("should I buy the S&P 500", "SPY"), ("sell tsx?", "XIU.TO")):
        body = client.post("/api/chat", json={"message": text}).json()
        assert body["trade_check"]["ticker"] == ticker and body["position"] is None


def test_chat_trade_answer_lists_the_latest_headlines():
    client.post("/api/market/refresh")
    body = client.post("/api/chat", json={"message": "should I sell enbridge"}).json()
    lines = body["headlines"]
    assert 1 <= len(lines) <= 3 and all(h["headline"] for h in lines)
    assert [h["date"] for h in lines] == sorted((h["date"] for h in lines), reverse=True)


def _fit(message, persona, lang="en"):
    client.post("/api/market/refresh")
    return client.post("/api/chat", json={"message": message, "holdings_persona": persona, "lang": lang}).json()["persona_fit"]


def test_persona_fit_depends_on_who_is_asking():
    # A panic-flagged sell: nobody should rush it, and each investor gets their own reasons.
    amira, robert = _fit("should I sell qqq", "amira"), _fit("should I sell qqq", "robert")
    assert amira["stance"] == robert["stance"] == "wait"
    assert amira["persona"]["name"] == "Amira" and robert["persona"]["name"] == "Robert"
    assert amira["why"] != robert["why"] and any("15+" in w for w in amira["why"])


def test_cautious_investor_is_steered_away_from_growth_style_buys():
    robert = _fit("should I buy nvidia", "robert")  # a dip, normally a fit, but NVDA is growth-style
    mateo = _fit("should I buy nvidia", "mateo")
    assert robert["stance"] == "wait" and any("prefer stability" in w for w in robert["why"])
    assert mateo["stance"] == "fits"


def test_hype_and_falling_knife_buys_are_not_waved_through():
    assert _fit("should I buy gold", "amira")["stance"] == "wait"
    assert _fit("should I buy gold", "robert")["stance"] == "careful"
    assert _fit("should I buy enbridge", "mateo")["stance"] == "careful"


def test_selling_something_not_held_says_so_and_french_works():
    assert _fit("should I sell qqq", "robert")["stance"] in ("wait", "fits", "careful")
    held = {h["ticker"] for h in client.get("/api/portfolio/robert").json()["holdings"]}
    fr = _fit("devrais-je vendre nvidia ?", "robert", "fr")
    assert "NVDA" in held or "Rien à vendre" in fr["headline"]
    assert "ans" in fr["why"][0]


def test_no_persona_means_no_fit_block():
    client.post("/api/market/refresh")
    assert client.post("/api/chat", json={"message": "should I sell qqq"}).json()["persona_fit"] is None


def test_headline_never_contradicts_the_stance():
    robert = _fit("should I buy nvidia", "robert")
    assert robert["stance"] == "wait" and "fits your plan" not in robert["headline"]
