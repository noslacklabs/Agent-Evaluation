from __future__ import annotations

import json
import time
import uuid
from typing import Any

import httpx

from adapters.base import AgentAdapter
from adapters.utils import get_path
from config import AGENT_TIMEOUT_SECONDS
from schemas import AgentResponse
from security import validate_endpoint


AGENT_REPORT_MARKER = "coworkai_agent"


def _unwrap_tool_output(output: Any) -> Any:
    """Langflow stores a serialised LangChain ToolMessage as a tool block's output."""
    if isinstance(output, dict) and output.get("type") == "tool" and "content" in output:
        artifact = output.get("artifact")
        return artifact if artifact is not None else output.get("content")
    return output


def _agent_report(value: Any) -> dict[str, Any] | None:
    """An Agent Configurator sub-agent returns its answer plus its own tool calls."""
    if isinstance(value, str):
        text = value.strip()
        if not (text.startswith("{") and AGENT_REPORT_MARKER in text):
            return None
        try:
            value = json.loads(text)
        except ValueError:
            return None
    if isinstance(value, dict) and value.get(AGENT_REPORT_MARKER):
        return value
    return None


def _tool_blocks(blocks: Any):
    """Yield tool_use blocks from a flat list or from the older nested `contents` layout."""
    for block in blocks or []:
        if not isinstance(block, dict):
            continue
        if block.get("type") == "tool_use":
            yield block
        elif block.get("contents"):
            yield from _tool_blocks(block["contents"])


def extract_tool_calls(blocks: Any, include_agent_calls: bool = True) -> list[dict[str, Any]]:
    """Tool calls in the order they happened.

    A call to a sub-agent is followed by the tool calls that sub-agent made, each
    tagged with `agent`. With include_agent_calls=False the sub-agent entries
    themselves are left out, so only real tools remain.
    """
    calls: list[dict[str, Any]] = []
    for block in _tool_blocks(blocks):
        name = block.get("name")
        if not name:
            continue
        output = _unwrap_tool_output(block.get("output"))
        report = _agent_report(output)
        if not report or include_agent_calls:
            entry: dict[str, Any] = {
                "name": name,
                "input_parameters": block.get("tool_input") or block.get("input") or {},
                "output": report.get("output") if report else output,
            }
            if block.get("error"):
                entry["error"] = block["error"]
            if report:
                entry["is_agent"] = True
            calls.append(entry)
        if report:
            for nested in report.get("tools_called") or []:
                if isinstance(nested, dict):
                    calls.append({"agent": report[AGENT_REPORT_MARKER], **nested})
    return calls


def solo_agent_ran(blocks: Any, agent: str) -> bool:
    """Whether the flow reports that it ran only this agent (Orchestrator "Solo Agent" switch)."""
    for block in _tool_blocks(blocks):
        report = _agent_report(_unwrap_tool_output(block.get("output")))
        if report and report.get("solo") is True and str(report[AGENT_REPORT_MARKER]).lower() == agent.lower():
            return True
    return False


def _as_chunks(value: Any) -> list[str]:
    if value is None or value == "":
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        chunks: list[str] = []
        for item in value:
            chunks.extend(_as_chunks(item))
        return chunks
    if isinstance(value, dict):
        for key in ("text", "page_content", "content"):
            if isinstance(value.get(key), str):
                return [value[key]]
        return [json.dumps(value, default=str)]
    return [str(value)]


class LangflowAdapter(AgentAdapter):
    """Runs a Langflow flow through POST /api/v1/run/{flow_id}.

    Config: base_url, flow_id, allow_private_network, timeout_seconds, and optionally
      tweaks                     Langflow tweaks sent with every run
      output_component           id or display name of the output to read the answer from
      output_path                dotted path to the answer, overrides the search
      retrieval_tools            tool names whose outputs count as retrieval context
      retrieval_output_component id or display name of an output that carries retrieved chunks
      include_agent_calls        false to list only real tools, not calls to sub-agents
      solo_agent                 name of the one agent this registration evaluates; the run is
                                 rejected unless the flow confirms it ran only that agent
    Secret: api_key (sent as x-api-key).
    """

    def _headers(self) -> dict[str, str]:
        headers = {str(k): str(v) for k, v in self.config.get("headers", {}).items()}
        api_key = self.secrets.get("api_key") or self.secrets.get("auth_value")
        if api_key:
            headers["x-api-key"] = api_key
        return headers

    @staticmethod
    def _matches(output: dict[str, Any], wanted: str | None) -> bool:
        if not wanted:
            return False
        return wanted in (output.get("component_id"), output.get("component_display_name"))

    @staticmethod
    def _outputs(data: dict[str, Any]) -> list[dict[str, Any]]:
        found = []
        for run in data.get("outputs") or []:
            for output in (run or {}).get("outputs") or []:
                if isinstance(output, dict):
                    found.append(output)
        return found

    @staticmethod
    def _message(output: dict[str, Any]) -> dict[str, Any] | None:
        message = (output.get("results") or {}).get("message")
        if isinstance(message, dict):
            # Field values may sit at the top level or under "data", depending on the output type.
            merged = dict(message.get("data") or {}) if isinstance(message.get("data"), dict) else {}
            merged.update({key: value for key, value in message.items() if key != "data"})
            return merged
        return None

    def _answer(self, data: dict[str, Any]) -> tuple[str, dict[str, Any]]:
        output_path = self.config.get("output_path")
        if output_path:
            value = get_path(data, output_path)
            if value is None:
                raise ValueError(f"Langflow output path '{output_path}' did not resolve to an answer")
            return str(value), {}

        retrieval_component = self.config.get("retrieval_output_component")
        wanted = self.config.get("output_component")
        candidates = []
        for output in self._outputs(data):
            message = self._message(output)
            if message is None or self._matches(output, retrieval_component):
                continue
            if wanted:
                if self._matches(output, wanted):
                    return str(message.get("text") or ""), message
                continue
            candidates.append(message)
        if wanted:
            raise ValueError(f"Langflow run returned no output from component '{wanted}'")
        for message in candidates:
            if message.get("text"):
                return str(message["text"]), message
        if candidates:
            return "", candidates[0]
        raise ValueError(
            "Langflow run returned no chat message. Check that the flow ends in a Chat Output "
            "and that output_type matches it."
        )

    def _retrieval_context(self, data: dict[str, Any], tool_calls: list[dict[str, Any]]) -> list[str]:
        chunks: list[str] = []
        retrieval_tools = set(self.config.get("retrieval_tools") or [])
        for call in tool_calls:
            if call.get("name") in retrieval_tools:
                chunks.extend(_as_chunks(call.get("output")))
        retrieval_component = self.config.get("retrieval_output_component")
        if retrieval_component:
            for output in self._outputs(data):
                if not self._matches(output, retrieval_component):
                    continue
                message = self._message(output)
                if message is not None:
                    chunks.extend(_as_chunks(message.get("text")))
                else:
                    chunks.extend(_as_chunks(output.get("results")))
        return chunks

    async def invoke(self, user_input: str, *, messages=None, session_id=None) -> AgentResponse:
        base_url = str(self.config.get("base_url", "")).rstrip("/")
        flow_id = self.config.get("flow_id")
        if not base_url or not flow_id:
            raise ValueError("Langflow connection needs base_url and flow_id")
        endpoint = validate_endpoint(
            f"{base_url}/api/v1/run/{flow_id}",
            bool(self.config.get("allow_private_network", False)),
        )
        # Without a session id Langflow uses the flow id, so every row would share one chat history.
        session = session_id or f"evaluator-{uuid.uuid4().hex}"
        payload: dict[str, Any] = {
            "input_value": user_input,
            "input_type": self.config.get("input_type", "chat"),
            "output_type": self.config.get("output_type", "chat"),
            "session_id": session,
        }
        tweaks = self.config.get("tweaks")
        if tweaks:
            payload["tweaks"] = tweaks

        started = time.perf_counter()
        timeout = float(self.config.get("timeout_seconds", AGENT_TIMEOUT_SECONDS))
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(endpoint, params={"stream": "false"}, headers=self._headers(), json=payload)
        elapsed = (time.perf_counter() - started) * 1000
        if response.status_code in (401, 403):
            raise ValueError(
                f"Langflow refused the request (HTTP {response.status_code}). Check the Langflow API key."
            )
        if response.status_code >= 400:
            try:
                detail = response.json().get("detail", response.text)
            except ValueError:
                detail = response.text
            if isinstance(detail, dict):
                detail = detail.get("message") or json.dumps(detail, default=str)
            raise ValueError(f"Langflow run failed (HTTP {response.status_code}): {str(detail)[:800]}")
        data = response.json()

        output, message = self._answer(data)
        solo_agent = self.config.get("solo_agent")
        if solo_agent and not solo_agent_ran(message.get("content_blocks"), str(solo_agent)):
            # Without this check the whole flow would be scored under one agent's name.
            raise ValueError(
                f"Langflow did not run agent '{solo_agent}' on its own. The flow changed since it was "
                "registered (the Orchestrator block was replaced, or the agent was renamed or disconnected). "
                "Register it again with 'Evaluate this agent'."
            )
        tool_calls = extract_tool_calls(
            message.get("content_blocks"),
            include_agent_calls=bool(self.config.get("include_agent_calls", True)),
        )
        usage = (message.get("properties") or {}).get("usage") or {}
        return AgentResponse(
            output=output,
            retrieval_context=self._retrieval_context(data, tool_calls),
            tools_called=tool_calls,
            usage=usage if isinstance(usage, dict) else {},
            metadata={
                "latency_ms": elapsed,
                "status_code": response.status_code,
                "session_id": session,
                "flow_id": flow_id,
            },
            raw_response=data,
        )

    async def test_connection(self, user_input: str) -> AgentResponse:
        # A fresh session each time, so earlier connection tests are not replayed as chat history.
        return await self.invoke(user_input, session_id=f"connection-test-{uuid.uuid4().hex}")
