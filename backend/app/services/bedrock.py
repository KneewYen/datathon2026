"""Grounded explanation synthesis through the real Amazon Bedrock Converse API."""

from __future__ import annotations

import json
import os
import re
from typing import Any, Dict

import boto3

from app.services.errors import ExternalServiceError, ServiceConfigurationError


TOKEN_PATTERN = re.compile(r"\{\{\s*([A-Za-z0-9_.\-]+)\s*\}\}")
MAX_ATTEMPTS = 3
FORWARD_LOOKING = re.compile(
    r"\b(could|would|will|may|might|likely to)\b[^.;]{0,40}\b(returns?|gains?|grow|outperform|profit)",
    re.IGNORECASE,
)


class WordingError(ExternalServiceError):
    """Grounded, digit-free answer whose wording sounds like a forecast."""

    def __init__(self, message: str, validated: Dict[str, Any]):
        super().__init__(message)
        self.validated = validated

SYSTEM_PROMPT = """You are the PortfolioGuard AI explainability component.
Use only the supplied evidence packet. Write no digits at all: no numbers, percentages,
amounts, or dates, and never repeat numbers from the user's question. You may name the
stress window as "the 2022 selloff". The platform appends every verified figure itself,
calculated in AWS Lambda, directly after your text, so describe direction and meaning only.
Address the investor by name and connect the evidence to their horizon, objective, and
preferences. Mention every governance warning that matters and say which scenario fits.
Every comparative word (higher, lower, larger, smaller, longer, shorter) must match the supplied
direction fields and must name its reference, for example "than the request" or "than the
current portfolio"; never attribute one scenario's result to another.
Describe returns only as historical observations; never say returns could, would, or will rise.
Do not expose hidden reasoning or provide financial advice. Keep the answer under seventy words.
Return JSON only with this shape:
{"answer": "concise answer with the material risk/return trade-off", "evidence_ids":
["only supplied evidence IDs"], "limitations": ["material limitations, without digits"]}.
"""


def client():
    region = os.getenv("AWS_REGION")
    if not region:
        raise ServiceConfigurationError("AWS_REGION is required for Amazon Bedrock")
    return boto3.client("bedrock-runtime", region_name=region)


def _extract_json(text: str) -> Dict[str, Any]:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.removeprefix("```json").removeprefix("```")
        cleaned = cleaned.removesuffix("```").strip()
    try:
        value = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise ExternalServiceError("Bedrock returned an invalid explanation document") from exc
    if not isinstance(value, dict):
        raise ExternalServiceError("Bedrock explanation must be a JSON object")
    return value


def _validate_result(
    result: Dict[str, Any], evidence_packet: Dict[str, Any], model_id: str
) -> Dict[str, Any]:
    allowed_ids = set(evidence_packet["allowed_evidence_ids"])
    allowed_tokens = set(evidence_packet.get("allowed_tokens", {}))
    answer = result.get("answer")
    cited_ids = result.get("evidence_ids")
    if not isinstance(answer, str) or not answer.strip():
        raise ExternalServiceError("Bedrock explanation is missing an answer")
    unknown_tokens = set(TOKEN_PATTERN.findall(answer)) - allowed_tokens
    if unknown_tokens:
        raise ExternalServiceError(
            "Bedrock explanation cited an unsupported evidence token: " + ", ".join(sorted(unknown_tokens))
        )
    prose = TOKEN_PATTERN.sub("", answer)
    for literal in evidence_packet.get("allowed_literals", []):
        prose = re.sub(rf"\b{re.escape(literal)}\b", "", prose)
    if re.search(r"\d", prose):
        raise ExternalServiceError(
            "Bedrock explanation attempted to introduce a numeric claim"
        )
    if (
        not isinstance(cited_ids, list)
        or not cited_ids
        or not all(isinstance(item, str) for item in cited_ids)
    ):
        raise ExternalServiceError("Bedrock explanation must cite evidence")
    supported = [item for item in cited_ids if item in allowed_ids]
    if not supported:
        raise ExternalServiceError("Bedrock explanation cited unsupported evidence")
    limitations = result.get("limitations", [])
    if not isinstance(limitations, list):
        raise ExternalServiceError("Bedrock limitations must be a list")
    validated = {
        "answer": TOKEN_PATTERN.sub(lambda match: "{{" + match.group(1) + "}}", answer.strip()),
        "evidence_ids": list(dict.fromkeys(supported)),
        "limitations": [str(item) for item in limitations if not re.search(r"\d", str(item))],
        "model_id": model_id,
    }
    if FORWARD_LOOKING.search(prose):
        raise WordingError(
            "Bedrock explanation used forecast-like wording about returns; describe them as historical",
            validated,
        )
    return validated

def synthesize(evidence_packet: Dict[str, Any]) -> Dict[str, Any]:
    model_id = os.getenv("BEDROCK_MODEL_ID")
    if not model_id:
        raise ServiceConfigurationError("BEDROCK_MODEL_ID is required")

    prompt = "Explain this verified evidence packet:\n" + json.dumps(
        evidence_packet, separators=(",", ":")
    )
    messages = [{"role": "user", "content": [{"text": prompt}]}]
    bedrock = client()

    def request() -> str:
        response = bedrock.converse(
            modelId=model_id,
            system=[{"text": SYSTEM_PROMPT}],
            messages=messages,
            inferenceConfig={"maxTokens": 600, "temperature": 0.0},
        )
        try:
            return response["output"]["message"]["content"][0]["text"]
        except (KeyError, IndexError, TypeError) as exc:
            raise ExternalServiceError(
                "Bedrock response did not contain explanation text"
            ) from exc

    last_error: ExternalServiceError | None = None
    for _ in range(MAX_ATTEMPTS):
        text = request()
        try:
            return _validate_result(_extract_json(text), evidence_packet, model_id)
        except ExternalServiceError as exc:
            last_error = exc
            messages.extend(
                [
                    {"role": "assistant", "content": [{"text": text}]},
                    {
                        "role": "user",
                        "content": [
                            {
                                "text": (
                                    f"Rejected by the validator: {exc}. Return the JSON again. "
                                    "Write no digits at all (the platform adds figures); "
                                    "cite only allowed_evidence_ids."
                                )
                            }
                        ],
                    },
                ]
            )
    assert last_error is not None
    if isinstance(last_error, WordingError):
        validated = last_error.validated
        return {
            **validated,
            "limitations": [
                *validated["limitations"],
                "The explanation's wording may sound forward-looking; every figure shown is historical only.",
            ],
        }
    raise last_error