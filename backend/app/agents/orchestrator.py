"""Global Orchestrator: detects intent, routes to the right agent, returns the answer."""
import re
from typing import Any, Dict, List

from app import store
from app.agents import account_advisor, account_creation, knowledge
from app.agents.signals import macro
from app.profiles import PROFILES

DISCLAIMER = "Simulation only. Not financial advice."


def _reply(answer: str, trace: List[Dict[str, Any]], **kw) -> Dict[str, Any]:
    return {
        "answer": answer,
        "trace": trace,
        "metrics": kw.get("metrics", {}),
        "sources": kw.get("sources", []),
        "warnings": kw.get("warnings", []),
        "proposal": kw.get("proposal"),
        "suggestions": kw.get("suggestions", []),
    }


def is_create_intent(text: str) -> bool:
    t = text.lower()
    return bool(re.search(r"(create|open|new|start|set up)", t) and re.search(r"account", t))


class GlobalOrchestrator:
    def chat(self, user_id: str, message: str) -> Dict[str, Any]:
        trace = [{"agent": "Global Orchestrator", "action": "detect intent"}]

        if is_create_intent(message):
            trace.append({"agent": "Account Advisor Agent", "action": "recommend account type and risk"})
            rec = account_advisor.recommend(message)
            if rec.get("needs") == "horizon":
                return _reply(
                    "What's the time horizon for this account?",
                    trace,
                    suggestions=[
                        "Create a short-term account",
                        "Create a mid-term account",
                        "Create a long-term account",
                    ],
                )
            action_id = store.new_id()
            store.PENDING[action_id] = {"user_id": user_id, "type": "create_account", "payload": rec}
            return _reply(
                f"I recommend a **{rec['account_type']}** account for {rec['horizon_label'].lower()}. "
                f"{rec['reason']} Suggested risk: **{rec['risk_label']}** (like {rec['persona']}). "
                "You can change the risk before approving.",
                trace,
                proposal={"id": action_id, "type": "create_account", **rec},
            )

        entry = knowledge.match(message)
        if entry:
            trace.append({"agent": "Knowledge Base Agent", "action": f"matched FAQ: {entry['id']}"})
            extra: Dict[str, Any] = {}
            answer = entry["answer"]
            if entry["id"] in ("recession", "rates"):
                trace.append({"agent": "Macro Signal Agent", "action": "read yield curve and unemployment"})
                sig = macro.recession_signals()
                extra = {k: sig.get(k, []) for k in ("metrics", "sources", "warnings")}
                if sig.get("notes"):
                    answer += "\n\n" + "\n".join(f"- {n}" for n in sig["notes"])
            if entry["id"] in ("recession", "volatility", "diversification"):
                accts = store.accounts(user_id)
                if accts:
                    trace.append({"agent": "Risk Agent", "action": "map exposure to your accounts"})
                    lines = [
                        f"- {a['name']} ({a['risk_label']}): handled by {a['horizon_agent']}"
                        + (", shortest horizon, most exposed to a near-term downturn" if a["horizon"] == "short" else "")
                        for a in accts
                    ]
                    answer += "\n\nYour accounts:\n" + "\n".join(lines)
            trace.append({"agent": "Explainability Agent", "action": "attach sources and limits"})
            extra.setdefault("warnings", []).append(DISCLAIMER)
            return _reply(answer, trace, **extra)

        return _reply(
            "I can answer common questions or help you open an account. Try one of these:",
            trace,
            suggestions=knowledge.suggestions() + ["Create a short-term account"],
        )

    def approve(self, action_id: str, risk: str = None) -> Dict[str, Any]:
        action = store.PENDING.pop(action_id, None)
        if action is None:
            return _reply("That proposal has expired.", [])
        payload = dict(action["payload"])
        if risk in PROFILES:
            payload["risk"] = risk
        acct = account_creation.create(action["user_id"], payload)
        return _reply(
            f"Created **{acct['name']}** ({acct['risk_label']}). It's managed by the {acct['horizon_agent']} "
            f"with {', '.join(acct['strategies'])} strategies.",
            [
                {"agent": "Global Orchestrator", "action": "user approved"},
                {"agent": "Account Creation Agent", "action": f"created {acct['name']}"},
            ],
            warnings=[DISCLAIMER],
        )

    def reject(self, action_id: str) -> Dict[str, Any]:
        store.PENDING.pop(action_id, None)
        return _reply("No problem, nothing was created.", [{"agent": "Global Orchestrator", "action": "user declined"}])
