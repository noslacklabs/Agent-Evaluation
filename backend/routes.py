from __future__ import annotations

import json
import re
import shutil
import uuid
import zipfile
from io import BytesIO
from pathlib import Path
from typing import Any

from fastapi import APIRouter, BackgroundTasks, File, Form, HTTPException, UploadFile
from fastapi.responses import PlainTextResponse, Response, StreamingResponse

from adapters import create_adapter
from agent_store import create_agent, delete_agent, get_agent, get_agent_runtime, list_agents, update_test_status
from config import DEEPEVAL_JUDGE_MODEL, MAX_UPLOAD_BYTES, PACKAGE_DIR, SERVICE_DIR, UPLOAD_DIR
from database import connection, row_to_dict, utc_now
from dataset_parser import DatasetValidationError, build_csv_template, build_jsonl_template, parse_dataset
from evaluation_service import create_run, get_run, list_runs, run_evaluation
from metrics_catalog import METRIC_BY_ID, list_metrics
from pdf_report import build_evaluation_report
from schemas import AgentCreate, ConnectionTestRequest, EvaluationCreate


router = APIRouter(prefix="/api")


def _validate_agent_config(connection_type: str, config: dict[str, Any]) -> None:
    required = {
        "rest_api": ["endpoint_url"],
        "websocket": ["websocket_url"],
        "openai_compatible": ["base_url", "model"],
        "framework": ["preset", "base_url"],
        "azure_openai": ["endpoint", "deployment"],
        "microsoft_foundry": ["project_endpoint"],
        "python_package": ["entrypoint"],
    }
    missing = [field for field in required.get(connection_type, []) if not config.get(field)]
    if connection_type == "microsoft_foundry" and not (config.get("agent_name") or config.get("agent_id")):
        missing.append("agent_name or agent_id")
    if missing:
        raise HTTPException(status_code=422, detail=f"Missing required connection fields: {', '.join(missing)}")


@router.get("/metrics")
def metrics_catalog():
    return {
        "metrics": list_metrics(),
        "deepeval_version": "4.x",
        "score_range": [0, 1],
        "default_judge_model": DEEPEVAL_JUDGE_MODEL,
    }


@router.get("/agents")
def agents_list():
    return {"agents": list_agents()}


@router.post("/agents", status_code=201)
def agents_create(request: AgentCreate):
    if request.connection_type == "python_package":
        raise HTTPException(status_code=422, detail="Use /api/agents/python-package to upload a Python agent")
    _validate_agent_config(request.connection_type, request.config)
    return create_agent(request.name, request.connection_type, request.config, request.secrets)


def _safe_extract(archive_path: Path, target: Path) -> None:
    with zipfile.ZipFile(archive_path) as archive:
        for member in archive.infolist():
            destination = (target / member.filename).resolve()
            if target.resolve() not in destination.parents and destination != target.resolve():
                raise HTTPException(status_code=400, detail="Archive contains an unsafe path")
            if member.file_size > MAX_UPLOAD_BYTES:
                raise HTTPException(status_code=413, detail="A package member exceeds the upload limit")
        archive.extractall(target)


@router.post("/agents/python-package", status_code=201)
async def agents_python_package(
    file: UploadFile = File(...),
    name: str = Form(...),
    entrypoint: str = Form(...),
):
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in {".zip", ".whl"}:
        raise HTTPException(status_code=415, detail="Python agents must be uploaded as .zip or .whl")
    if not re.fullmatch(r"[A-Za-z_][\w.]*:[A-Za-z_]\w*", entrypoint):
        raise HTTPException(status_code=422, detail="Entrypoint must use module:function format")
    content = await file.read(MAX_UPLOAD_BYTES + 1)
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="Package exceeds the configured upload limit")
    package_id = uuid.uuid4().hex
    target = PACKAGE_DIR / package_id
    target.mkdir(parents=True, exist_ok=False)
    archive_path = target / f"agent{suffix}"
    archive_path.write_bytes(content)
    try:
        extracted = target / "src"
        extracted.mkdir()
        _safe_extract(archive_path, extracted)
    except (zipfile.BadZipFile, HTTPException):
        shutil.rmtree(target, ignore_errors=True)
        raise
    config = {"entrypoint": entrypoint, "package_path": str(extracted)}
    return create_agent(name, "python_package", config, {}, str(extracted))


@router.post("/agents/manifest", status_code=201)
async def agents_manifest(file: UploadFile = File(...)):
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in {".json", ".yaml", ".yml"}:
        raise HTTPException(status_code=415, detail="Agent manifests must be JSON or YAML")
    content = await file.read(MAX_UPLOAD_BYTES + 1)
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="Manifest exceeds the upload limit")
    try:
        if suffix == ".json":
            manifest = json.loads(content)
        else:
            import yaml
            manifest = yaml.safe_load(content)
        request = AgentCreate.model_validate(manifest)
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"Invalid agent manifest: {exc}") from exc
    if request.connection_type == "python_package":
        raise HTTPException(status_code=422, detail="Python manifests must be paired with a package upload")
    _validate_agent_config(request.connection_type, request.config)
    return create_agent(request.name, request.connection_type, request.config, request.secrets)


@router.post("/agents/{agent_id}/test")
async def agents_test(agent_id: str, request: ConnectionTestRequest):
    agent = get_agent_runtime(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    try:
        response = await create_adapter(agent["connection_type"], agent["config"], agent["secrets"]).test_connection(request.input)
        update_test_status(agent_id, True, "Connection successful")
        return {"ok": True, "output": response.output, "metadata": response.metadata, "usage": response.usage}
    except Exception as exc:
        update_test_status(agent_id, False, str(exc))
        raise HTTPException(status_code=400, detail=f"Connection test failed: {exc}") from exc


@router.delete("/agents/{agent_id}", status_code=204)
def agents_delete(agent_id: str):
    if not delete_agent(agent_id):
        raise HTTPException(status_code=404, detail="Agent not found")


@router.get("/datasets")
def datasets_list():
    with connection() as conn:
        rows = conn.execute("SELECT * FROM datasets ORDER BY created_at DESC").fetchall()
    return {"datasets": [row_to_dict(row, ("columns_json", "warnings_json")) for row in rows]}


@router.post("/datasets", status_code=201)
async def datasets_create(file: UploadFile = File(...), name: str | None = Form(default=None)):
    filename = Path(file.filename or "dataset").name
    content = await file.read(MAX_UPLOAD_BYTES + 1)
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="Dataset exceeds the configured upload limit")
    try:
        cases, columns, warnings = parse_dataset(filename, content)
    except (DatasetValidationError, UnicodeDecodeError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    dataset_id = uuid.uuid4().hex
    stored_path = UPLOAD_DIR / f"{dataset_id}{Path(filename).suffix.lower()}"
    stored_path.write_bytes(content)
    dataset_name = (name or Path(filename).stem).strip()[:120]
    with connection() as conn:
        conn.execute(
            """INSERT INTO datasets (id, name, source_filename, file_path, row_count, columns_json, warnings_json, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (dataset_id, dataset_name, filename, str(stored_path), len(cases), json.dumps(columns), json.dumps(warnings), utc_now()),
        )
        conn.executemany(
            "INSERT INTO dataset_cases (dataset_id, row_number, case_json) VALUES (?, ?, ?)",
            [(dataset_id, index, json.dumps(case)) for index, case in enumerate(cases, 1)],
        )
        conn.commit()
    with connection() as conn:
        row = conn.execute("SELECT * FROM datasets WHERE id = ?", (dataset_id,)).fetchone()
    return row_to_dict(row, ("columns_json", "warnings_json"))


@router.get("/datasets/template.csv", response_class=PlainTextResponse)
def datasets_template():
    return PlainTextResponse(
        build_csv_template(),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="agent-evaluation-template.csv"'},
    )


@router.get("/datasets/template.jsonl", response_class=PlainTextResponse)
def datasets_jsonl_template():
    return PlainTextResponse(
        build_jsonl_template(),
        media_type="application/x-ndjson",
        headers={"Content-Disposition": 'attachment; filename="agent-evaluation-template.jsonl"'},
    )


@router.get("/datasets/template.xlsx")
def datasets_xlsx_template():
    path = SERVICE_DIR / "templates" / "agent-evaluation-template.xlsx"
    if not path.exists():
        raise HTTPException(status_code=500, detail="XLSX template is not installed")
    return Response(
        content=path.read_bytes(),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": 'attachment; filename="agent-evaluation-template.xlsx"'},
    )


@router.get("/evaluations")
def evaluations_list():
    return {"runs": list_runs()}


@router.post("/evaluations", status_code=202)
def evaluations_create(request: EvaluationCreate, background_tasks: BackgroundTasks):
    unknown = [metric_id for metric_id in request.metric_ids if metric_id not in METRIC_BY_ID]
    if unknown:
        raise HTTPException(status_code=422, detail=f"Unknown metrics: {', '.join(unknown)}")
    unavailable = [METRIC_BY_ID[item] for item in request.metric_ids if METRIC_BY_ID[item]["availability"] != "ready"]
    if unavailable:
        labels = ", ".join(f"{item['name']} ({item['availability']})" for item in unavailable)
        raise HTTPException(status_code=422, detail=f"These metrics need additional integration before a black-box run: {labels}")
    with connection() as conn:
        dataset_row = conn.execute("SELECT columns_json FROM datasets WHERE id = ?", (request.dataset_id,)).fetchone()
    if dataset_row:
        columns = set(json.loads(dataset_row["columns_json"]))
        dataset_only = {"expected_output", "expected_tools", "chatbot_role", "available_tools"}
        missing_by_metric = {
            metric_id: sorted(set(METRIC_BY_ID[metric_id]["required_fields"]) & dataset_only - columns)
            for metric_id in request.metric_ids
        }
        missing_by_metric = {key: value for key, value in missing_by_metric.items() if value}
        if missing_by_metric:
            detail = "; ".join(f"{metric_id}: {', '.join(fields)}" for metric_id, fields in missing_by_metric.items())
            raise HTTPException(status_code=422, detail=f"Dataset is missing required columns — {detail}")
    try:
        run = create_run(
            request.name or f"Evaluation {utc_now()[:10]}",
            request.agent_id,
            request.dataset_id,
            request.metric_ids,
            request.metric_config,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    background_tasks.add_task(run_evaluation, run["id"])
    return run


@router.get("/evaluations/{run_id}")
def evaluations_get(run_id: str):
    run = get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Evaluation run not found")
    return run


@router.get("/evaluations/{run_id}/report.pdf")
def evaluations_report(run_id: str):
    run = get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Evaluation run not found")
    report = build_evaluation_report(run)
    safe_name = re.sub(r"[^A-Za-z0-9._-]+", "-", run["name"]).strip("-") or "evaluation-report"
    return StreamingResponse(
        BytesIO(report),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{safe_name}.pdf"'},
    )
