from __future__ import annotations

from adapters.azure_openai import AzureOpenAIAdapter
from adapters.foundry import MicrosoftFoundryAdapter
from adapters.framework import FrameworkAdapter
from adapters.langflow import LangflowAdapter
from adapters.openai_compatible import OpenAICompatibleAdapter
from adapters.python_package import PythonPackageAdapter
from adapters.rest import RESTAdapter
from adapters.websocket import WebSocketAdapter


ADAPTERS = {
    "rest_api": RESTAdapter,
    "websocket": WebSocketAdapter,
    "python_package": PythonPackageAdapter,
    "openai_compatible": OpenAICompatibleAdapter,
    "framework": FrameworkAdapter,
    "langflow": LangflowAdapter,
    "azure_openai": AzureOpenAIAdapter,
    "microsoft_foundry": MicrosoftFoundryAdapter,
}


def create_adapter(connection_type: str, config: dict, secrets: dict | None = None):
    try:
        adapter_cls = ADAPTERS[connection_type]
    except KeyError as exc:
        raise ValueError(f"Unsupported connection type: {connection_type}") from exc
    return adapter_cls(config, secrets)
