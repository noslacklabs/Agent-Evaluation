from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from schemas import AgentResponse


class AgentAdapter(ABC):
    def __init__(self, config: dict[str, Any], secrets: dict[str, str] | None = None):
        self.config = config
        self.secrets = secrets or {}

    @abstractmethod
    async def invoke(
        self,
        user_input: str,
        *,
        messages: list[dict[str, Any]] | None = None,
        session_id: str | None = None,
    ) -> AgentResponse:
        raise NotImplementedError

    async def test_connection(self, user_input: str) -> AgentResponse:
        return await self.invoke(user_input, session_id="connection-test")

