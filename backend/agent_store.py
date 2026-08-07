from __future__ import annotations

import json
import uuid
from typing import Any

from database import connection, row_to_dict, utc_now
from encryption import decrypt_secret, encrypt_secret


PUBLIC_JSON_FIELDS = ("config_json",)


def create_agent(name: str, connection_type: str, config: dict[str, Any], secrets: dict[str, str], package_path: str | None = None) -> dict[str, Any]:
    agent_id = uuid.uuid4().hex
    now = utc_now()
    encrypted = {key: encrypt_secret(value) for key, value in secrets.items() if value}
    with connection() as conn:
        conn.execute(
            """INSERT INTO agents
               (id, name, connection_type, config_json, secrets_json, package_path, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (agent_id, name, connection_type, json.dumps(config), json.dumps(encrypted), package_path, now, now),
        )
        conn.commit()
    return get_agent(agent_id)


def _public_agent(row) -> dict[str, Any] | None:
    item = row_to_dict(row, PUBLIC_JSON_FIELDS)
    if item is None:
        return None
    secret_names = sorted(json.loads(item.pop("secrets_json") or "{}").keys())
    item["configured_secrets"] = secret_names
    item["has_package"] = bool(item.get("package_path"))
    item.pop("package_path", None)
    return item


def list_agents() -> list[dict[str, Any]]:
    with connection() as conn:
        return [_public_agent(row) for row in conn.execute("SELECT * FROM agents ORDER BY created_at DESC")]


def get_agent(agent_id: str) -> dict[str, Any] | None:
    with connection() as conn:
        return _public_agent(conn.execute("SELECT * FROM agents WHERE id = ?", (agent_id,)).fetchone())


def get_agent_runtime(agent_id: str) -> dict[str, Any] | None:
    with connection() as conn:
        row = conn.execute("SELECT * FROM agents WHERE id = ?", (agent_id,)).fetchone()
    if not row:
        return None
    item = dict(row)
    item["config"] = json.loads(item.pop("config_json"))
    item["secrets"] = {key: decrypt_secret(value) for key, value in json.loads(item.pop("secrets_json") or "{}").items()}
    if item.get("package_path"):
        item["config"]["package_path"] = item["package_path"]
    return item


def update_test_status(agent_id: str, ok: bool, message: str) -> None:
    now = utc_now()
    with connection() as conn:
        conn.execute(
            "UPDATE agents SET status = ?, last_tested_at = ?, last_test_message = ?, updated_at = ? WHERE id = ?",
            ("ready" if ok else "failed", now, message[:1000], now, agent_id),
        )
        conn.commit()


def delete_agent(agent_id: str) -> bool:
    with connection() as conn:
        cursor = conn.execute("DELETE FROM agents WHERE id = ?", (agent_id,))
        conn.commit()
        return cursor.rowcount > 0

