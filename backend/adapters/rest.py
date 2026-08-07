from __future__ import annotations

import time
from typing import Any

import httpx

from adapters.base import AgentAdapter
from adapters.utils import get_path, render_template
from config import AGENT_TIMEOUT_SECONDS
from schemas import AgentResponse
from security import validate_endpoint


class RESTAdapter(AgentAdapter):
    def _headers(self) -> dict[str, str]:
        headers = {str(k): str(v) for k, v in self.config.get("headers", {}).items()}
        auth_type = self.config.get("auth_type", "none")
        secret = self.secrets.get("auth_value") or self.secrets.get("api_key")
        if auth_type == "bearer" and secret:
            headers["Authorization"] = f"Bearer {secret}"
        elif auth_type == "api_key" and secret:
            headers[self.config.get("api_key_header", "X-API-Key")] = secret
        return headers

    async def invoke(self, user_input: str, *, messages=None, session_id=None) -> AgentResponse:
        endpoint = validate_endpoint(
            self.config["endpoint_url"],
            bool(self.config.get("allow_private_network", False)),
        )
        variables = {
            "input": user_input,
            "messages": messages or [{"role": "user", "content": user_input}],
            "session_id": session_id or "",
        }
        template = self.config.get("request_template") or {"input": "{{input}}"}
        payload = render_template(template, variables)
        started = time.perf_counter()
        async with httpx.AsyncClient(timeout=float(self.config.get("timeout_seconds", AGENT_TIMEOUT_SECONDS))) as client:
            response = await client.request(
                self.config.get("method", "POST").upper(),
                endpoint,
                headers=self._headers(),
                json=payload,
            )
            response.raise_for_status()
            data = response.json()
        elapsed = (time.perf_counter() - started) * 1000
        mapping = self.config.get("response_mapping", {})
        output = get_path(data, mapping.get("output", "output"))
        if output is None:
            raise ValueError(
                f"Response mapping '{mapping.get('output', 'output')}' did not resolve to an output"
            )
        retrieval_context = get_path(data, mapping.get("retrieval_context"), []) or []
        if isinstance(retrieval_context, str):
            retrieval_context = [retrieval_context]
        tools_called = get_path(data, mapping.get("tools_called"), []) or []
        usage = get_path(data, mapping.get("usage"), {}) or {}
        return AgentResponse(
            output=str(output),
            retrieval_context=[str(item) for item in retrieval_context],
            tools_called=tools_called if isinstance(tools_called, list) else [],
            usage=usage if isinstance(usage, dict) else {},
            metadata={"latency_ms": elapsed, "status_code": response.status_code},
            raw_response=data,
        )
