from __future__ import annotations

from adapters.rest import RESTAdapter


class FrameworkAdapter(RESTAdapter):
    def __init__(self, config, secrets=None):
        preset = config.get("preset", "custom_webhook")
        base = config.get("base_url", "").rstrip("/")
        transformed = dict(config)
        if preset == "langflow":
            flow_id = config.get("flow_id")
            transformed.update({
                "endpoint_url": f"{base}/api/v1/run/{flow_id}",
                "request_template": {"input_value": "{{input}}", "output_type": "chat", "input_type": "chat"},
                "response_mapping": {"output": config.get("output_path", "outputs.0.outputs.0.results.message.text")},
            })
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

