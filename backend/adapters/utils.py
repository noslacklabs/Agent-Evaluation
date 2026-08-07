from __future__ import annotations

import json
import re
from typing import Any


TOKEN_RE = re.compile(r"\{\{\s*([\w.]+)\s*\}\}")


def get_path(data: Any, path: str | None, default: Any = None) -> Any:
    if not path:
        return default
    current = data
    for part in path.split("."):
        if isinstance(current, list):
            try:
                current = current[int(part)]
            except (ValueError, IndexError):
                return default
        elif isinstance(current, dict):
            if part not in current:
                return default
            current = current[part]
        else:
            return default
    return current


def render_template(value: Any, variables: dict[str, Any]) -> Any:
    if isinstance(value, dict):
        return {key: render_template(item, variables) for key, item in value.items()}
    if isinstance(value, list):
        return [render_template(item, variables) for item in value]
    if not isinstance(value, str):
        return value

    full_match = TOKEN_RE.fullmatch(value)
    if full_match:
        return get_path(variables, full_match.group(1), "")

    def replace(match: re.Match[str]) -> str:
        found = get_path(variables, match.group(1), "")
        if isinstance(found, (dict, list)):
            return json.dumps(found)
        return str(found)

    return TOKEN_RE.sub(replace, value)


def extract_openai_response(data: dict[str, Any]) -> str:
    chat = get_path(data, "choices.0.message.content")
    if isinstance(chat, str):
        return chat
    if isinstance(data.get("output_text"), str):
        return data["output_text"]
    chunks: list[str] = []
    for item in data.get("output", []) or []:
        for content in item.get("content", []) or []:
            text = content.get("text") if isinstance(content, dict) else None
            if text:
                chunks.append(str(text))
    return "\n".join(chunks)

