"""In-memory store for the demo. Replace with a database later."""
import uuid
from typing import Any, Dict, List

ACCOUNTS: Dict[str, List[Dict[str, Any]]] = {}
PENDING: Dict[str, Dict[str, Any]] = {}


def new_id() -> str:
    return uuid.uuid4().hex[:8]


def accounts(user_id: str) -> List[Dict[str, Any]]:
    return ACCOUNTS.setdefault(user_id, [])
