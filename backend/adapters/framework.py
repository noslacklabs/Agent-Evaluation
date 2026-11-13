from __future__ import annotations

from adapters.langflow import LangflowAdapter
from adapters.rest import RESTAdapter


class FrameworkAdapter(RESTAdapter):
    def __init__(self, config, secrets=None):
        preset = config.get("preset", "custom_webhook")
        base = config.get("base_url", "").rstrip("/")
        transformed = dict(config)
        # The Langflow preset is handled by the dedicated adapter (see invoke below):
        # it sends the API key and a session id per row, and reads tool calls.
        self._langflow = LangflowAdapter(config, secrets) if preset == "langflow" else None
        if preset == "langflow":
            transformed["endpoint_url"] = f"{base}/api/v1/run/{config.get('flow_id')}"
        elif preset == "langserve":
            transformed.update({
                "endpoint_url": f"{base}/invoke",
                "request_template": {"input": {"input": "{{input}}"}},
                "response_mapping": {"output": config.get("output_path", "output")},
            })
        elif preset == "fastapi_agent":
            transformed.update({
                "endpoint_url": config.get("endpoint_url") or f"{base}/invoke",
                "request_template": config.get("request_template") or {"input": "{{input}}", "session_id": "{{session_id}}"},
                "response_mapping": config.get("response_mapping") or {"output": "output"},
            })
        else:
            transformed["endpoint_url"] = config.get("endpoint_url") or base
        super().__init__(transformed, secrets)

    async def invoke(self, user_input, *, messages=None, session_id=None):
        if self._langflow is not None:
            return await self._langflow.invoke(user_input, messages=messages, session_id=session_id)
        return await super().invoke(user_input, messages=messages, session_id=session_id)

    async def test_connection(self, user_input):
        if self._langflow is not None:
            return await self._langflow.test_connection(user_input)
        return await super().test_connection(user_input)
