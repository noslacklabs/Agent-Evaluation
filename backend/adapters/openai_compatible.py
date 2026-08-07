from __future__ import annotations

import time

import httpx

from adapters.base import AgentAdapter
from adapters.utils import extract_openai_response
from config import AGENT_TIMEOUT_SECONDS
from schemas import AgentResponse
from security import validate_endpoint


class OpenAICompatibleAdapter(AgentAdapter):
    async def invoke(self, user_input: str, *, messages=None, session_id=None) -> AgentResponse:
        base = self.config["base_url"].rstrip("/")
        endpoint = base if base.endswith("/chat/completions") else f"{base}/chat/completions"
        validate_endpoint(endpoint, bool(self.config.get("allow_private_network", False)))
        headers = {"Content-Type": "application/json"}
        if self.secrets.get("api_key"):
            headers["Authorization"] = f"Bearer {self.secrets['api_key']}"
        payload = {
            "model": self.config["model"],
            "messages": messages or [{"role": "user", "content": user_input}],
            "temperature": self.config.get("temperature", 0),
            "stream": False,
        }
        started = time.perf_counter()
        async with httpx.AsyncClient(timeout=float(self.config.get("timeout_seconds", AGENT_TIMEOUT_SECONDS))) as client:
            response = await client.post(endpoint, headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()
        output = extract_openai_response(data)
        if not output:
            raise ValueError("OpenAI-compatible response did not contain assistant text")
        return AgentResponse(
            output=output,
            usage=data.get("usage") or {},
            metadata={"latency_ms": (time.perf_counter() - started) * 1000, "model": data.get("model")},
            raw_response=data,
        )

