from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, HttpUrl, model_validator


ConnectionType = Literal[
    "rest_api",
    "websocket",
    "python_package",
    "openai_compatible",
    "framework",
    "langflow",
    "azure_openai",
    "microsoft_foundry",
]


class AgentCreate(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    connection_type: ConnectionType
    config: dict[str, Any] = Field(default_factory=dict)
    secrets: dict[str, str] = Field(default_factory=dict)


class EvaluationCreate(BaseModel):
    name: str | None = Field(default=None, max_length=120)
    agent_id: str
    dataset_id: str
    metric_ids: list[str] = Field(min_length=1)
    metric_config: dict[str, Any] = Field(default_factory=dict)


class ConnectionTestRequest(BaseModel):
    input: str = "Reply with a short confirmation that the connection works."


class AgentResponse(BaseModel):
    output: str
    retrieval_context: list[str] = Field(default_factory=list)
    tools_called: list[dict[str, Any]] = Field(default_factory=list)
    mcp: dict[str, Any] = Field(default_factory=dict)
    usage: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)
    raw_response: Any = None
