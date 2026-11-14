from typing import Any, Dict, List

from pydantic import BaseModel


class AgentResult(BaseModel):
    """Common response schema shared by all agents."""

    agent: str
    summary: str = ""
    metrics: Dict[str, Any] = {}
    data_sources: List[str] = []
    assumptions: List[str] = []
    warnings: List[str] = []


class Agent:
    name = "agent"

    def run(self, context: Dict[str, Any]) -> AgentResult:
        raise NotImplementedError
