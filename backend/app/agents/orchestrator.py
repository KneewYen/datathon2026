"""Global Orchestrator: detects intent, routes to the right agent, returns the answer."""
import re
from typing import Any, Dict, List

from app import store
from app.agents import account_creation, knowledge, profile
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
            trace.append({"agent": "Investor Profile Agent", "action": "read horizon and risk, recommend account"})
            rec = profile.recommend(message)
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
            trace.append({"agent": "Governance Agent", "action": "check fit with profile, require user approval"})
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
            trace[0]["action"] = f"detect intent: question ({entry['id']}), route to {', '.join(entry['agents'])}"
            extra: Dict[str, Any] = {"metrics": {}, "sources": [f"Knowledge base: {entry['id']}"], "warnings": []}
            answer = entry["answer"]
            for agent in entry["agents"]:
                if agent == "Macro Signal Agent":
                    trace.append({"agent": agent, "action": "read yield curve and unemployment (Market Data)"})
                    sig = macro.recession_signals()
                    extra["metrics"].update(sig.get("metrics", {}))
                    extra["sources"] += sig.get("sources", [])
                    extra["warnings"] += sig.get("warnings", [])
                    if sig.get("notes"):
                        answer += "\n\n" + "\n".join(f"- {n}" for n in sig["notes"])
                elif agent == "Risk Agent":
                    accts = store.accounts(user_id)
                    trace.append({"agent": agent, "action": "map exposure to your accounts" if accts else "no accounts yet"})
                    if accts:
                        lines = [
                            f"- {a['name']} ({a['risk_label']}): handled by {a['horizon_agent']}"
                            + (", shortest horizon, most exposed to a near-term downturn" if a["horizon"] == "short" else "")
                            for a in accts
                        ]
                        answer += "\n\nYour accounts:\n" + "\n".join(lines)
                else:
                    trace.append({"agent": agent, "action": "answer from knowledge base"})
            trace.append({"agent": "Explainability Agent", "action": "attach sources and limits"})
            extra["warnings"].append(DISCLAIMER)
            return _reply(answer, trace, **extra)

        return _reply(
            "I don't have that in my knowledge base yet. Try one of these:",
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
                {"agent": "Governance Agent", "action": "user approved"},
                {"agent": "Account Creation Agent", "action": f"created {acct['name']}"},
                {"agent": acct["horizon_agent"], "action": f"assigned {', '.join(acct['strategies'])}"},
            ],
            warnings=[DISCLAIMER],
        )

    def reject(self, action_id: str) -> Dict[str, Any]:
        store.PENDING.pop(action_id, None)
        return _reply("No problem, nothing was created.", [{"agent": "Global Orchestrator", "action": "user declined"}])
