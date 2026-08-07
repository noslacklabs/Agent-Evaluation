from __future__ import annotations

import unittest
from io import BytesIO
from pathlib import Path

from openpyxl import load_workbook
from pypdf import PdfReader

from dataset_parser import build_jsonl_template, parse_dataset
from pdf_report import build_evaluation_report


class TemplateAndPdfTests(unittest.TestCase):
    def test_jsonl_template_is_uploadable(self):
        cases, columns, _ = parse_dataset("template.jsonl", build_jsonl_template().encode("utf-8"))
        self.assertEqual(cases[0]["input"], "What is the refund policy?")
        self.assertIn("expected_output", columns)

    def test_xlsx_template_has_upload_headers_and_field_guide(self):
        path = Path(__file__).resolve().parents[1] / "templates" / "agent-evaluation-template.xlsx"
        workbook = load_workbook(path, read_only=True, data_only=True)
        self.assertEqual(workbook.sheetnames, ["Evaluation Cases", "Field Guide"])
        self.assertEqual(workbook["Evaluation Cases"]["A1"].value, "question")
        cases, columns, _ = parse_dataset("template.xlsx", path.read_bytes())
        self.assertEqual(len(cases), 1)
        self.assertIn("input", columns)

    def test_pdf_report_is_readable_and_contains_summary(self):
        report = build_evaluation_report({
            "name": "Refund benchmark",
            "agent_name": "Support agent",
            "dataset_name": "Refund cases",
            "status": "completed",
            "progress_total": 1,
            "summary": {
                "overall_score": 0.91,
                "scored_cases": 1,
                "average_agent_latency_ms": 125,
                "error_count": 0,
                "metrics": [{"metric_id": "answer_relevancy", "average_score": 0.91, "pass_rate": 1, "min_score": 0.91, "max_score": 0.91, "evaluated": 1, "errors": 0}],
            },
            "results": [{"dataset_row": 1, "metric_id": "answer_relevancy", "score": 0.91, "input_preview": "What is the refund policy?", "output_preview": "Thirty days.", "reason": "Relevant answer."}],
        })
        reader = PdfReader(BytesIO(report))
        text = "\n".join(page.extract_text() or "" for page in reader.pages)
        self.assertGreaterEqual(len(reader.pages), 2)
        self.assertIn("Refund benchmark", text)
        self.assertIn("Case-level evidence", text)
