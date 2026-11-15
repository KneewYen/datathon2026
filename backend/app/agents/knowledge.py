"""Knowledge base tool: matches a question to an FAQ entry and the wiki agents that own it."""
import json
from pathlib import Path
from typing import Any, Dict, Optional

FAQ = json.loads((Path(__file__).parents[1] / "knowledge" / "faq.json").read_text())


def match(message: str) -> Optional[Dict[str, Any]]:
    text = message.lower()
    best, score = None, 0
    for entry in FAQ:
        hits = sum(len(k) for k in entry["keywords"] if k in text)
        if hits > score:
            best, score = entry, hits
    return best


def suggestions():
    return [e["question"] for e in FAQ[:5]]
