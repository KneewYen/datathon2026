from typing import Any, Dict

from app.agents.profile import PERSONAS

HORIZON_BY_PERSONA = {"amira": "long_term", "mateo": "mid_term", "robert": "short_term"}


class GlobalOrchestrator:
    """Understands the question, routes to a horizon agent, combines results."""

    def run(self, persona_id: str, message: str) -> Dict[str, Any]:
        profile = PERSONAS.get(persona_id)
        if profile is None:
            return {"answer": f"Unknown persona: {persona_id}", "warnings": ["unknown_persona"]}
        horizon = HORIZON_BY_PERSONA[persona_id]
        # TODO: Profile -> Horizon -> Strategies (+ Signals, Risk) -> Governance -> Explainability
        return {
            "answer": "Not implemented yet.",
            "trace": [{"step": "orchestrator", "persona": persona_id, "horizon": horizon}],
        }
