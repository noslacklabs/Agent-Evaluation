from __future__ import annotations

import csv
import io
import json
from pathlib import Path
from typing import Any, Iterable


ALIASES = {
    "question": "input",
    "prompt": "input",
    "query": "input",
    "ground_truth": "expected_output",
    "groundtruth": "expected_output",
    "reference_answer": "expected_output",
    "answer": "expected_output",
    "contexts": "retrieval_context",
    "retrieved_context": "retrieval_context",
    "tool_calls": "tools_called",
    "reference_tools": "expected_tools",
    "conversation": "turns",
    "role": "chatbot_role",
}

JSON_FIELDS = {
    "context",
    "retrieval_context",
    "tools_called",
    "expected_tools",
    "available_tools",
    "turns",
    "mcp_servers",
    "mcp_calls",
    "metadata",
}

TEMPLATE_HEADERS = [
    "question",
    "ground_truth",
    "retrieval_context",
    "expected_tools",
    "turns",
    "chatbot_role",
    "available_tools",
    "metadata",
]
TEMPLATE_EXAMPLE = {
    "question": "What is the refund policy?",
    "ground_truth": "Refunds are available within 30 days.",
    "retrieval_context": ["Customers may request a refund within 30 days of purchase."],
    "expected_tools": [],
    "turns": [],
    "chatbot_role": "Helpful customer support assistant",
    "available_tools": [],
    "metadata": {"category": "refunds"},
}


class DatasetValidationError(ValueError):
    pass


def _normalize_key(value: str) -> str:
    key = value.strip().lower().replace(" ", "_").replace("-", "_")
    return ALIASES.get(key, key)


def _parse_json_field(value: Any, field: str) -> Any:
    if value is None or value == "":
        return [] if field != "metadata" else {}
    if isinstance(value, (list, dict)):
        return value
    if not isinstance(value, str):
        return value
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        if field in {"context", "retrieval_context"}:
            return [part.strip() for part in value.split("||") if part.strip()]
        raise DatasetValidationError(f"Field '{field}' must contain valid JSON")
    return parsed


def normalize_case(raw: dict[str, Any], row_number: int) -> dict[str, Any]:
    case: dict[str, Any] = {}
    for key, value in raw.items():
        if key is None:
            continue
        normalized = _normalize_key(str(key))
        if normalized in JSON_FIELDS:
            value = _parse_json_field(value, normalized)
        if isinstance(value, float) and value != value:
            value = None
        case[normalized] = value
    if not case.get("input"):
        turns = case.get("turns") or []
        first_user = next((turn for turn in turns if turn.get("role") == "user"), None)
        if first_user:
            case["input"] = first_user.get("content")
    if not isinstance(case.get("input"), str) or not case["input"].strip():
        raise DatasetValidationError(f"Row {row_number}: missing question/input")
    case["input"] = case["input"].strip()
    if case.get("expected_output") is not None:
        case["expected_output"] = str(case["expected_output"])
    return case


def _read_csv(content: bytes) -> list[dict[str, Any]]:
    text = content.decode("utf-8-sig")
    return list(csv.DictReader(io.StringIO(text)))


def _read_jsonl(content: bytes) -> list[dict[str, Any]]:
    rows = []
    for line_number, line in enumerate(content.decode("utf-8-sig").splitlines(), 1):
        if not line.strip():
            continue
        try:
            item = json.loads(line)
        except json.JSONDecodeError as exc:
            raise DatasetValidationError(f"Line {line_number}: invalid JSON") from exc
        if not isinstance(item, dict):
            raise DatasetValidationError(f"Line {line_number}: each JSONL value must be an object")
        rows.append(item)
    return rows


def _read_xlsx(content: bytes) -> list[dict[str, Any]]:
    try:
        from openpyxl import load_workbook
    except ImportError as exc:
        raise DatasetValidationError("XLSX support requires openpyxl") from exc
    workbook = load_workbook(io.BytesIO(content), read_only=True, data_only=True)
    sheet = workbook.active
    iterator = sheet.iter_rows(values_only=True)
    try:
        headers = [str(value).strip() if value is not None else "" for value in next(iterator)]
    except StopIteration as exc:
        raise DatasetValidationError("Workbook is empty") from exc
    return [dict(zip(headers, values)) for values in iterator if any(value is not None for value in values)]


def parse_dataset(filename: str, content: bytes) -> tuple[list[dict[str, Any]], list[str], list[str]]:
    suffix = Path(filename).suffix.lower()
    if suffix == ".csv":
        raw_rows = _read_csv(content)
    elif suffix == ".jsonl":
        raw_rows = _read_jsonl(content)
    elif suffix == ".xlsx":
        raw_rows = _read_xlsx(content)
    else:
        raise DatasetValidationError("Supported dataset formats are .csv, .jsonl, and .xlsx")
    if not raw_rows:
        raise DatasetValidationError("Dataset contains no test cases")
    if len(raw_rows) > 10_000:
        raise DatasetValidationError("A dataset may contain at most 10,000 rows")

    cases: list[dict[str, Any]] = []
    errors: list[str] = []
    for index, raw in enumerate(raw_rows, 2 if suffix in {".csv", ".xlsx"} else 1):
        try:
            cases.append(normalize_case(raw, index))
        except DatasetValidationError as exc:
            errors.append(str(exc))
    if errors:
        preview = "; ".join(errors[:8])
        if len(errors) > 8:
            preview += f"; and {len(errors) - 8} more"
        raise DatasetValidationError(preview)

    columns = sorted({key for case in cases for key in case})
    warnings = []
    if "expected_output" not in columns:
        warnings.append("No ground truth column was found; reference-based metrics will be unavailable.")
    if "retrieval_context" not in columns:
        warnings.append("No retrieval context column was found; RAG grounding metrics require the agent response mapping to supply it.")
    return cases, columns, warnings


def build_csv_template() -> str:
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(TEMPLATE_HEADERS)
    writer.writerow([
        json.dumps(TEMPLATE_EXAMPLE[field]) if field in JSON_FIELDS else TEMPLATE_EXAMPLE[field]
        for field in TEMPLATE_HEADERS
    ])
    return output.getvalue()


def build_jsonl_template() -> str:
    return json.dumps(TEMPLATE_EXAMPLE, ensure_ascii=False) + "\n"
