from __future__ import annotations

import asyncio
import time

import httpx

from adapters.base import AgentAdapter
from adapters.utils import extract_openai_response
from config import AGENT_TIMEOUT_SECONDS
from schemas import AgentResponse
from security import validate_endpoint


class MicrosoftFoundryAdapter(AgentAdapter):
    def _headers(self) -> dict[str, str]:
        token = self.secrets.get("entra_token") or self.secrets.get("api_key")
        if not token:
            raise ValueError("A Microsoft Entra bearer token is required")
        return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    async def invoke(self, user_input: str, *, messages=None, session_id=None) -> AgentResponse:
        if self.config.get("api_mode", "responses") == "classic_threads":
            return await self._invoke_classic(user_input)
        base = self.config["project_endpoint"].rstrip("/")
        endpoint = f"{base}/openai/v1/responses"
        validate_endpoint(endpoint, bool(self.config.get("allow_private_network", False)))
        reference = {"type": "agent_reference", "name": self.config.get("agent_name") or self.config.get("agent_id")}
        if self.config.get("agent_version"):
            reference["version"] = self.config["agent_version"]
        payload = {"input": user_input, "agent_reference": reference}
        if self.config.get("conversation_id"):
            payload["conversation"] = self.config["conversation_id"]
        started = time.perf_counter()
        async with httpx.AsyncClient(timeout=float(self.config.get("timeout_seconds", AGENT_TIMEOUT_SECONDS))) as client:
            response = await client.post(endpoint, headers=self._headers(), json=payload)
            response.raise_for_status()
            data = response.json()
        output = extract_openai_response(data)
        if not output:
            raise ValueError("Foundry response did not contain assistant text")
        tool_calls = [item for item in data.get("output", []) if item.get("type") in {"function_call", "mcp_call"}]
        return AgentResponse(
            output=output,
            tools_called=tool_calls,
            usage=data.get("usage") or {},
            metadata={"latency_ms": (time.perf_counter() - started) * 1000, "response_id": data.get("id")},
            raw_response=data,
        )

    async def _invoke_classic(self, user_input: str) -> AgentResponse:
        base = self.config["project_endpoint"].rstrip("/")
        validate_endpoint(base, bool(self.config.get("allow_private_network", False)))
        params = {"api-version": self.config.get("api_version", "v1")}
        started = time.perf_counter()
        timeout = float(self.config.get("timeout_seconds", AGENT_TIMEOUT_SECONDS))
        async with httpx.AsyncClient(timeout=timeout, headers=self._headers()) as client:
            thread = (await client.post(f"{base}/threads", params=params, json={})).raise_for_status().json()
            thread_id = thread["id"]
            (await client.post(f"{base}/threads/{thread_id}/messages", params=params, json={"role": "user", "content": user_input})).raise_for_status()
            run = (await client.post(f"{base}/threads/{thread_id}/runs", params=params, json={"agent_id": self.config["agent_id"]})).raise_for_status().json()
            for _ in range(max(1, int(timeout))):
                if run.get("status") not in {"queued", "in_progress"}:
                    break
                await asyncio.sleep(1)
                run = (await client.get(f"{base}/threads/{thread_id}/runs/{run['id']}", params=params)).raise_for_status().json()
            if run.get("status") != "completed":
                raise RuntimeError(f"Foundry run ended with status {run.get('status')}")
            messages = (await client.get(f"{base}/threads/{thread_id}/messages", params={**params, "order": "desc", "limit": 20})).raise_for_status().json()
        assistant = next((item for item in messages.get("data", []) if item.get("role") == "assistant"), None)
        parts = []
        for block in (assistant or {}).get("content", []):
            text = block.get("text", {})
            if isinstance(text, dict) and text.get("value"):
                parts.append(text["value"])
        if not parts:
            raise ValueError("Foundry thread completed without an assistant message")
        return AgentResponse(output="\n".join(parts), metadata={"latency_ms": (time.perf_counter() - started) * 1000, "thread_id": thread_id, "run_id": run.get("id")})
