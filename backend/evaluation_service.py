from __future__ import annotations

import asyncio
import json
import math
import time
import uuid
from collections import defaultdict
from statistics import mean
from typing import Any

from adapters import create_adapter
from agent_store import get_agent_runtime
from database import connection, row_to_dict, utc_now
from metric_runner import build_test_cases, measure


def create_run(name: str, agent_id: str, dataset_id: str, metric_ids: list[str], metric_config: dict[str, Any]) -> dict[str, Any]:
    run_id = uuid.uuid4().hex
    with connection() as conn:
        dataset = conn.execute("SELECT row_count FROM datasets WHERE id = ?", (dataset_id,)).fetchone()
        agent = conn.execute("SELECT id FROM agents WHERE id = ?", (agent_id,)).fetchone()
        if not dataset:
            raise ValueError("Dataset not found")
        if not agent:
            raise ValueError("Agent not found")
        conn.execute(
            """INSERT INTO evaluation_runs
               (id, name, agent_id, dataset_id, metric_ids_json, metric_config_json, status, progress_total, created_at)
               VALUES (?, ?, ?, ?, ?, ?, 'queued', ?, ?)""",
            (run_id, name, agent_id, dataset_id, json.dumps(metric_ids), json.dumps(metric_config), dataset["row_count"], utc_now()),
        )
        conn.commit()
    return get_run(run_id, include_results=False)


def get_run(run_id: str, include_results: bool = True) -> dict[str, Any] | None:
    with connection() as conn:
        row = conn.execute(
            """SELECT r.*, a.name AS agent_name, a.connection_type,
                      d.name AS dataset_name, d.source_filename AS dataset_filename
               FROM evaluation_runs r
               JOIN agents a ON a.id = r.agent_id
               JOIN datasets d ON d.id = r.dataset_id
               WHERE r.id = ?""",
            (run_id,),
        ).fetchone()
        run = row_to_dict(row, ("metric_ids_json", "metric_config_json", "summary_json"))
        if run and include_results:
            result_rows = conn.execute(
                "SELECT * FROM evaluation_results WHERE run_id = ? ORDER BY dataset_row, metric_id", (run_id,)
            ).fetchall()
            run["results"] = [row_to_dict(item, ("metadata_json",)) for item in result_rows]
    return run


def list_runs() -> list[dict[str, Any]]:
    with connection() as conn:
        rows = conn.execute(
            """SELECT r.*, a.name AS agent_name, d.name AS dataset_name
               FROM evaluation_runs r
               JOIN agents a ON a.id = r.agent_id
               JOIN datasets d ON d.id = r.dataset_id
               ORDER BY r.created_at DESC"""
        ).fetchall()
    return [row_to_dict(row, ("metric_ids_json", "metric_config_json", "summary_json")) for row in rows]


def _insert_result(run_id: str, row_number: int, metric_id: str, *, score=None, passed=None, reason=None, error=None, latency_ms=None, input_preview=None, output_preview=None, metadata=None) -> None:
    with connection() as conn:
        conn.execute(
            """INSERT INTO evaluation_results
               (run_id, dataset_row, metric_id, score, passed, reason, error, latency_ms, input_preview, output_preview, metadata_json, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (run_id, row_number, metric_id, score, None if passed is None else int(passed), reason, error, latency_ms, (input_preview or "")[:800], (output_preview or "")[:1600], json.dumps(metadata or {}), utc_now()),
        )
        conn.commit()


def _build_summary(run_id: str) -> dict[str, Any]:
    with connection() as conn:
        rows = [dict(row) for row in conn.execute("SELECT * FROM evaluation_results WHERE run_id = ?", (run_id,))]
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[row["metric_id"]].append(row)
    metrics = []
    all_scores: list[float] = []
    for metric_id, items in grouped.items():
        scores = [float(item["score"]) for item in items if item["score"] is not None]
        all_scores.extend(scores)
        metrics.append({
            "metric_id": metric_id,
            "average_score": mean(scores) if scores else None,
            "pass_rate": sum(1 for item in items if item["passed"] == 1) / len(scores) if scores else None,
            "evaluated": len(scores),
            "errors": sum(1 for item in items if item["error"]),
            "min_score": min(scores) if scores else None,
            "max_score": max(scores) if scores else None,
        })
    scored_rows = sorted({item["dataset_row"] for item in rows if item["score"] is not None})
    latencies = [item["latency_ms"] for item in rows if item["latency_ms"] is not None]
    sorted_latencies = sorted(latencies)
    p95_index = max(0, math.ceil(len(sorted_latencies) * 0.95) - 1) if sorted_latencies else 0
    return {
        "overall_score": mean(all_scores) if all_scores else None,
        "metrics": sorted(metrics, key=lambda item: item["metric_id"]),
        "scored_cases": len(scored_rows),
        "result_count": len(rows),
        "error_count": sum(1 for item in rows if item["error"]),
        "average_agent_latency_ms": mean(latencies) if latencies else None,
        "p95_agent_latency_ms": sorted_latencies[p95_index] if sorted_latencies else None,
        "score_distribution": {
            "excellent": sum(1 for score in all_scores if score >= 0.8),
            "good": sum(1 for score in all_scores if 0.6 <= score < 0.8),
            "needs_work": sum(1 for score in all_scores if score < 0.6),
        },
    }


async def run_evaluation(run_id: str) -> None:
    run = get_run(run_id, include_results=False)
    if not run:
        return
    with connection() as conn:
        conn.execute("UPDATE evaluation_runs SET status = 'running', started_at = ? WHERE id = ?", (utc_now(), run_id))
        case_rows = conn.execute(
            "SELECT row_number, case_json FROM dataset_cases WHERE dataset_id = ? ORDER BY row_number", (run["dataset_id"],)
        ).fetchall()
        conn.commit()
    agent = get_agent_runtime(run["agent_id"])
    if not agent:
        _fail_run(run_id, "Agent not found")
        return
    adapter = create_adapter(agent["connection_type"], agent["config"], agent["secrets"])

    try:
        for progress, row in enumerate(case_rows, 1):
            case = json.loads(row["case_json"])
            response = None
            started = time.perf_counter()
            try:
                response = await adapter.invoke(case["input"], session_id=f"{run_id}:{row['row_number']}")
                invocation_ms = (time.perf_counter() - started) * 1000
                single, conversation, available_tools = build_test_cases(case, response)
                for metric_id in run["metric_ids"]:
                    config = {**run["metric_config"].get("defaults", {}), **run["metric_config"].get(metric_id, {})}
                    try:
                        result = await measure(metric_id, config, single, conversation, available_tools)
                        _insert_result(
                            run_id, row["row_number"], metric_id,
                            score=result["score"], passed=result["passed"], reason=result["reason"],
                            latency_ms=invocation_ms, input_preview=case["input"], output_preview=response.output,
                            metadata={"evaluation_model": result.get("evaluation_model"), "evaluation_cost": result.get("evaluation_cost"), "agent_usage": response.usage},
                        )
                    except Exception as exc:
                        _insert_result(run_id, row["row_number"], metric_id, error=str(exc), latency_ms=invocation_ms, input_preview=case["input"], output_preview=response.output)
            except Exception as exc:
                invocation_ms = (time.perf_counter() - started) * 1000
                for metric_id in run["metric_ids"]:
                    _insert_result(run_id, row["row_number"], metric_id, error=f"Agent invocation failed: {exc}", latency_ms=invocation_ms, input_preview=case["input"])
            with connection() as conn:
                conn.execute("UPDATE evaluation_runs SET progress_current = ? WHERE id = ?", (progress, run_id))
                conn.commit()
            await asyncio.sleep(0)

        summary = _build_summary(run_id)
        status = "completed_with_errors" if summary["error_count"] else "completed"
        with connection() as conn:
            conn.execute(
                "UPDATE evaluation_runs SET status = ?, summary_json = ?, completed_at = ? WHERE id = ?",
                (status, json.dumps(summary), utc_now(), run_id),
            )
            conn.commit()
    except Exception as exc:
        _fail_run(run_id, str(exc))


def _fail_run(run_id: str, error: str) -> None:
    with connection() as conn:
        conn.execute(
            "UPDATE evaluation_runs SET status = 'failed', error = ?, completed_at = ? WHERE id = ?",
            (error[:4000], utc_now(), run_id),
        )
        conn.commit()
