from __future__ import annotations

import time
from urllib.parse import quote

import httpx

from adapters.base import AgentAdapter
from adapters.utils import extract_openai_response
from config import AGENT_TIMEOUT_SECONDS
from schemas import AgentResponse
from security import validate_endpoint


class AzureOpenAIAdapter(AgentAdapter):
    def _headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        auth_method = self.config.get("auth_method", "api_key")
        if auth_method == "api_key":
            headers["api-key"] = self.secrets.get("api_key", "")
        else:
            token = self.secrets.get("entra_token")
            if not token:
                raise ValueError("An Entra bearer token is required for this authentication mode")
            headers["Authorization"] = f"Bearer {token}"
        return headers

    async def invoke(self, user_input: str, *, messages=None, session_id=None) -> AgentResponse:
        base = self.config["endpoint"].rstrip("/")
        deployment = quote(self.config["deployment"], safe="")
        api_type = self.config.get("api_type", "responses")
        api_version = self.config.get("api_version", "v1")
        if api_type == "responses":
            endpoint = f"{base}/openai/v1/responses?api-version={api_version}"
            payload = {"model": self.config["deployment"], "input": user_input}
        else:
            endpoint = f"{base}/openai/deployments/{deployment}/chat/completions?api-version={api_version}"
            payload = {"messages": messages or [{"role": "user", "content": user_input}], "temperature": 0}
        validate_endpoint(endpoint, bool(self.config.get("allow_private_network", False)))
        started = time.perf_counter()
        async with httpx.AsyncClient(timeout=float(self.config.get("timeout_seconds", AGENT_TIMEOUT_SECONDS))) as client:
            response = await client.post(endpoint, headers=self._headers(), json=payload)
            response.raise_for_status()
            data = response.json()
        output = extract_openai_response(data)
        if not output:
            raise ValueError("Azure OpenAI response did not contain assistant text")
        return AgentResponse(
            output=output,
            usage=data.get("usage") or {},
            metadata={"latency_ms": (time.perf_counter() - started) * 1000, "api_type": api_type},
            raw_response=data,
        )

