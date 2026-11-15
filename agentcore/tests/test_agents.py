"""The five AgentCore agents, run in-process with a fake invoker standing in for the runtimes.

The model step is replaced by "call the tool", so these tests check the wiring, the order, the
hand-offs and the persona-aware verdicts, not what a model says. Needs the Strands SDK:
``pip install strands-agents bedrock-agentcore pytest`` and run with ``ENGINE=local``.
"""

from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path

import pytest

pytest.importorskip("strands")
pytest.importorskip("bedrock_agentcore")

ROOT = Path(__file__).resolve().parents[2]
os.environ.setdefault("ENGINE", "local")
os.environ.pop("DATA_BUCKET", None)
os.environ.pop("BEDROCK_MODEL_ID", None)
sys.path.insert(0, str(ROOT / "agentcore"))
sys.path.insert(0, str(ROOT / "backend"))


def load(name: str):
    spec = importlib.util.spec_from_file_location(f"pg_{name}", ROOT / "agentcore" / name / "main.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    # No model in tests: the "agent" simply calls its tool.
    module.run_agent = lambda _n, _s, tools, _p, captured, key: (tools[0](), captured[key])[1]
    return module


AGENTS = {name: load(name) for name in ("intake", "market", "classifier", "explainer", "orchestrator")}
ARNS = {"INTAKE_AGENT_ARN": "intake", "MARKET_AGENT_ARN": "market", "CLASSIFIER_AGENT_ARN": "classifier", "EXPLAINER_AGENT_ARN": "explainer"}
CALLS: list = []


@pytest.fixture(autouse=True)
def runtimes(monkeypatch):
    CALLS.clear()
    for env, name in ARNS.items():
        monkeypatch.setenv(env, f"arn:aws:bedrock-agentcore:us-east-1:000000000000:runtime/{name}")


def fake_invoker(arn: str, request: dict, session: str):
    name = arn.rsplit("/", 1)[-1]
    CALLS.append(name)
    return AGENTS[name].work(request["payload"])


def check(persona: str, ticker: str = "NVDA", account: str | None = None, action: str = "sell", **extra):
    request = {"action": action, "ticker": ticker, "persona": persona, "account_type": account, "live": True, "lang": "en", **extra}
    return AGENTS["orchestrator"].work(request, fake_invoker, use_model=False)


def test_each_agent_is_its_own_runtime_called_in_order():
    out = check("robert")
    assert CALLS == ["intake", "market", "classifier", "explainer"]
    assert [s["agent"] for s in out["trace"]] == ["Intake", "Market", "Classifier", "Explainer"]
    assert [s["runtime"] for s in out["trace"]] == ["intake", "market", "classifier", "explainer"]


def test_the_same_sale_is_judged_by_who_is_selling():
    assert check("amira")["verdict"] == "panic_risk"
    assert check("mateo")["verdict"] == "mixed"
    robert = check("robert")
    assert robert["intake"]["risk_band"] == "low" and robert["verdict"] == "evidence_supported"
    assert check("amira", account="RRSP")["verdict"] == "mixed"  # the RRSP lowers the band one step


def test_the_result_has_the_shape_the_app_expects():
    out = check("amira")
    for key in ("verdict", "driver", "evidence", "move_size", "profile_adjustment", "trace", "intake", "explanation"):
        assert key in out
    assert out["persona_fit"]["persona"]["name"] == "Amira"


def test_a_step_run_out_of_order_pulls_in_the_earlier_ones():
    run = AGENTS["orchestrator"].Run({"action": "sell", "ticker": "NVDA", "persona": "robert", "live": True}, fake_invoker)
    run.classify()  # the model jumped straight to the Classifier
    assert CALLS == ["intake", "market", "classifier"]
    assert run.finish()["trace"][-1]["agent"] == "Explainer" and CALLS[-1] == "explainer"


def test_a_specialist_failure_reaches_the_caller():
    with pytest.raises(LookupError):  # market not refreshed
        check("amira", live=False)


def test_the_orchestrator_needs_an_action_and_a_ticker():
    common = sys.modules["common"]
    with pytest.raises(common.AgentFailure):
        AGENTS["orchestrator"].work({"ticker": "NVDA"}, fake_invoker, use_model=False)


def test_entrypoints_wrap_results_in_the_envelope():
    reply = AGENTS["market"].invoke({"payload": {"ticker": "NVDA", "live": False}})
    assert reply["ok"] is False and reply["status"] == 409
    reply = AGENTS["market"].invoke({"payload": {"ticker": "NVDA", "live": True}})
    assert reply["ok"] is True and reply["result"]["ticker"] == "NVDA"
