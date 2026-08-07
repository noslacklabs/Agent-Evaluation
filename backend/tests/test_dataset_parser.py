from __future__ import annotations

import io
import json
import unittest

from dataset_parser import DatasetValidationError, parse_dataset


class DatasetParserTests(unittest.TestCase):
    def test_csv_aliases_and_json_fields(self):
        content = (
            'question,ground_truth,retrieval_context,expected_tools\n'
            '"What is the policy?","Thirty days","[""30 day policy""]","[]"\n'
        ).encode()
        cases, columns, warnings = parse_dataset("cases.csv", content)
        self.assertEqual(cases[0]["input"], "What is the policy?")
        self.assertEqual(cases[0]["expected_output"], "Thirty days")
        self.assertEqual(cases[0]["retrieval_context"], ["30 day policy"])
        self.assertIn("expected_output", columns)
        self.assertEqual(warnings, [])

    def test_jsonl_preserves_rich_fields(self):
        raw = {
            "input": "Find the weather",
            "expected_output": "Sunny",
            "tools_called": [{"name": "weather", "arguments": {"city": "Pune"}}],
            "turns": [{"role": "user", "content": "I live in Pune"}],
        }
        cases, columns, _ = parse_dataset("cases.jsonl", (json.dumps(raw) + "\n").encode())
        self.assertEqual(cases[0]["tools_called"][0]["name"], "weather")
        self.assertIn("turns", columns)

    def test_missing_input_is_rejected(self):
        with self.assertRaises(DatasetValidationError):
            parse_dataset("cases.csv", b"ground_truth\nanswer\n")

    def test_xlsx(self):
        try:
            from openpyxl import Workbook
        except ImportError:
            self.skipTest("openpyxl is not installed")
        workbook = Workbook()
        sheet = workbook.active
        sheet.append(["question", "ground_truth"])
        sheet.append(["Hello", "Hi"])
        stream = io.BytesIO()
        workbook.save(stream)
        cases, _, _ = parse_dataset("cases.xlsx", stream.getvalue())
        self.assertEqual(cases[0]["expected_output"], "Hi")


if __name__ == "__main__":
    unittest.main()

