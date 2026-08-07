from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any, Iterator

from config import DB_PATH, ensure_directories


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@contextmanager
def connection() -> Iterator[sqlite3.Connection]:
    ensure_directories()
    conn = sqlite3.connect(DB_PATH, timeout=30, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
    finally:
        conn.close()


def init_db() -> None:
    with connection() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS agents (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                connection_type TEXT NOT NULL,
                config_json TEXT NOT NULL,
                secrets_json TEXT NOT NULL DEFAULT '{}',
                package_path TEXT,
                status TEXT NOT NULL DEFAULT 'untested',
                last_tested_at TEXT,
                last_test_message TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS datasets (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                source_filename TEXT NOT NULL,
                file_path TEXT NOT NULL,
                row_count INTEGER NOT NULL,
                columns_json TEXT NOT NULL,
                warnings_json TEXT NOT NULL DEFAULT '[]',
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS dataset_cases (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                dataset_id TEXT NOT NULL REFERENCES datasets(id) ON DELETE CASCADE,
                row_number INTEGER NOT NULL,
                case_json TEXT NOT NULL,
                UNIQUE(dataset_id, row_number)
            );

            CREATE TABLE IF NOT EXISTS evaluation_runs (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                agent_id TEXT NOT NULL REFERENCES agents(id),
                dataset_id TEXT NOT NULL REFERENCES datasets(id),
                metric_ids_json TEXT NOT NULL,
                metric_config_json TEXT NOT NULL DEFAULT '{}',
                status TEXT NOT NULL,
                progress_current INTEGER NOT NULL DEFAULT 0,
                progress_total INTEGER NOT NULL DEFAULT 0,
                summary_json TEXT,
                error TEXT,
                created_at TEXT NOT NULL,
                started_at TEXT,
                completed_at TEXT
            );

            CREATE TABLE IF NOT EXISTS evaluation_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id TEXT NOT NULL REFERENCES evaluation_runs(id) ON DELETE CASCADE,
                dataset_row INTEGER NOT NULL,
                metric_id TEXT NOT NULL,
                score REAL,
                passed INTEGER,
                reason TEXT,
                error TEXT,
                latency_ms REAL,
                input_preview TEXT,
                output_preview TEXT,
                metadata_json TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_results_run ON evaluation_results(run_id);
            CREATE INDEX IF NOT EXISTS idx_runs_created ON evaluation_runs(created_at DESC);
            """
        )
        conn.commit()


def row_to_dict(row: sqlite3.Row | None, json_fields: tuple[str, ...] = ()) -> dict[str, Any] | None:
    if row is None:
        return None
    result = dict(row)
    for field in json_fields:
        if field in result and result[field] is not None:
            result[field.removesuffix("_json")] = json.loads(result.pop(field))
    return result

