from __future__ import annotations

import asyncio
import inspect
import json
import time
from typing import Any

from adapters.base import AgentAdapter
from adapters.utils import get_path, render_template
from config import AGENT_TIMEOUT_SECONDS
from schemas import AgentResponse
from security import validate_websocket_endpoint


class WebSocketAdapter(AgentAdapter):
    def _headers(self) -> dict[str, str]:
        headers = {str(key): str(value) for key, value in self.config.get("headers", {}).items()}
        auth_type = self.config.get("auth_type", "none")
        secret = self.secrets.get("auth_value") or self.secrets.get("api_key")
        if auth_type == "bearer" and secret:
            headers["Authorization"] = f"Bearer {secret}"
        elif auth_type == "api_key" and secret:
            headers[self.config.get("api_key_header", "X-API-Key")] = secret
        return headers

    def _normalize(self, frames: list[dict[str, Any]], elapsed_ms: float) -> AgentResponse:
        mapping = self.config.get("response_mapping", {})
        output_path = mapping.get("output", "output")
        output_parts: list[str] = []
        retrieval_context: list[str] = []
        tools_called: list[dict[str, Any]] = []
        usage: dict[str, Any] = {}

        for frame in frames:
            output = get_path(frame, output_path)
            if output is not None:
                output_parts.append(str(output))
            context = get_path(frame, mapping.get("retrieval_context"), []) or []
            if isinstance(context, str):
                context = [context]
            retrieval_context.extend(str(item) for item in context)
            calls = get_path(frame, mapping.get("tools_called"), []) or []
            if isinstance(calls, list):
                tools_called.extend(item for item in calls if isinstance(item, dict))
            mapped_usage = get_path(frame, mapping.get("usage"), {}) or {}
            if isinstance(mapped_usage, dict):
                usage.update(mapped_usage)

        if not output_parts:
            raise ValueError(f"WebSocket response mapping '{output_path}' did not resolve to output text")
        separator = str(self.config.get("chunk_separator", ""))
        return AgentResponse(
            output=separator.join(output_parts),
            retrieval_context=list(dict.fromkeys(retrieval_context)),
            tools_called=tools_called,
            usage=usage,
            metadata={"latency_ms": elapsed_ms, "websocket_frames": len(frames)},
            raw_response=frames,
        )

    async def invoke(self, user_input: str, *, messages=None, session_id=None) -> AgentResponse:
        try:
            import websockets
        except ImportError as exc:
            raise RuntimeError("WebSocket connections require the 'websockets' package") from exc

        endpoint = validate_websocket_endpoint(
            self.config["websocket_url"],
            bool(self.config.get("allow_private_network", False)),
        )
        variables = {
            "input": user_input,
            "messages": messages or [{"role": "user", "content": user_input}],
            "session_id": session_id or "",
        }
        payload = render_template(
            self.config.get("request_template") or {"input": "{{input}}", "session_id": "{{session_id}}"},
            variables,
        )
        timeout = float(self.config.get("timeout_seconds", AGENT_TIMEOUT_SECONDS))
        response_mode = self.config.get("response_mode", "single")
        done_path = self.config.get("done_path", "type")
        done_value = self.config.get("done_value", "done")
        frames: list[dict[str, Any]] = []
        started = time.perf_counter()

        connect_options = {
            "open_timeout": timeout,
            "close_timeout": min(timeout, 10),
            "ping_interval": 20,
        }
        header_parameter = "additional_headers" if "additional_headers" in inspect.signature(websockets.connect).parameters else "extra_headers"
        connect_options[header_parameter] = self._headers() or None
        async with websockets.connect(endpoint, **connect_options) as socket:
            await socket.send(json.dumps(payload))
            while True:
                raw = await asyncio.wait_for(socket.recv(), timeout=timeout)
                if isinstance(raw, bytes):
                    raw = raw.decode("utf-8")
                try:
                    frame = json.loads(raw)
                except json.JSONDecodeError:
                    frame = {"output": raw}
                if not isinstance(frame, dict):
                    frame = {"output": str(frame)}
                if response_mode == "stream" and get_path(frame, done_path) == done_value:
                    break
                frames.append(frame)
                if response_mode == "single":
                    break
                if len(frames) >= int(self.config.get("max_frames", 500)):
                    raise ValueError("WebSocket response exceeded the configured frame limit")

        return self._normalize(frames, (time.perf_counter() - started) * 1000)
