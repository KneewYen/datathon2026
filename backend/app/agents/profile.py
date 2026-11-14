"""Investor profile lookup for the three fictional challenge personas."""

from app.domain.presets import PERSONAS


def get_persona(persona_id: str) -> dict:
    try:
        return PERSONAS[persona_id]
    except KeyError as exc:
        raise ValueError(f"unknown persona: {persona_id}") from exc
