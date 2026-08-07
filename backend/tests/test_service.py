from __future__ import annotations

import io
import os
import tempfile
import unittest


class ServiceSmokeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp_dir = tempfile.TemporaryDirectory()
        os.environ["EVALUATOR_DATA_DIR"] = cls.temp_dir.name
        os.environ["OPENAI_API_KEY"] = "test-key-for-construction-only"
        from fastapi.testclient import TestClient
        from main import app

        cls.client_context = TestClient(app)
        cls.client = cls.client_context.__enter__()

    @classmethod
    def tearDownClass(cls):
        cls.client_context.__exit__(None, None, None)
        cls.temp_dir.cleanup()

    def test_health_and_metric_catalog(self):
        health = self.client.get("/health")
        self.assertEqual(health.status_code, 200)
        self.assertEqual(health.json()["service"], "agent-evaluator")
        catalog = self.client.get("/api/metrics")
        self.assertEqual(catalog.status_code, 200)
        self.assertGreaterEqual(len(catalog.json()["metrics"]), 30)
        self.assertTrue(catalog.json()["default_judge_model"])

    def test_local_frontend_origins_are_allowed(self):
        for origin in ("http://localhost:5173", "http://127.0.0.1:5173", "http://localhost:5174"):
            with self.subTest(origin=origin):
                response = self.client.options(
                    "/api/metrics",
                    headers={
                        "Origin": origin,
                        "Access-Control-Request-Method": "GET",
                    },
                )
                self.assertEqual(response.status_code, 200, response.text)
                self.assertEqual(response.headers["access-control-allow-origin"], origin)

    def test_agent_secrets_are_redacted(self):
        response = self.client.post(
            "/api/agents",
            json={
                "name": "Smoke agent",
                "connection_type": "openai_compatible",
                "config": {"base_url": "https://example.com/v1", "model": "agent"},
                "secrets": {"api_key": "secret"},
            },
        )
        self.assertEqual(response.status_code, 201, response.text)
        body = response.json()
        self.assertNotIn("secrets", body)
        self.assertEqual(body["configured_secrets"], ["api_key"])

    def test_dataset_upload_and_reference_validation(self):
        content = b"question,ground_truth\nWhat is two plus two?,Four\n"
        response = self.client.post(
            "/api/datasets",
            data={"name": "Math smoke"},
            files={"file": ("cases.csv", io.BytesIO(content), "text/csv")},
        )
        self.assertEqual(response.status_code, 201, response.text)
        dataset = response.json()
        self.assertEqual(dataset["row_count"], 1)
        self.assertIn("expected_output", dataset["columns"])

        agents = self.client.get("/api/agents").json()["agents"]
        run = self.client.post(
            "/api/evaluations",
            json={
                "agent_id": agents[0]["id"],
                "dataset_id": dataset["id"],
                "metric_ids": ["tool_correctness"],
                "metric_config": {},
            },
        )
        self.assertEqual(run.status_code, 422)
        self.assertIn("expected_tools", run.json()["detail"])

    def test_current_deepeval_metric_factories_construct(self):
        from config import DEEPEVAL_JUDGE_MODEL
        from deepeval.test_case import ToolCall
        from metric_runner import build_metric

        metric_ids = [
            "g_eval", "conversational_g_eval", "answer_relevancy", "faithfulness",
            "contextual_precision", "contextual_recall", "contextual_relevancy",
            "argument_correctness", "tool_correctness", "turn_relevancy",
            "role_adherence", "knowledge_retention", "conversation_completeness",
            "goal_accuracy", "turn_faithfulness", "turn_contextual_precision",
            "turn_contextual_recall", "turn_contextual_relevancy",
        ]
        for metric_id in metric_ids:
            with self.subTest(metric_id=metric_id):
                self.assertIsNotNone(build_metric(metric_id, {"judge_model": DEEPEVAL_JUDGE_MODEL}, []))
        available = [ToolCall(name="lookup", description="Lookup a value")]
        self.assertIsNotNone(build_metric("tool_use", {"judge_model": DEEPEVAL_JUDGE_MODEL}, available))
        self.assertIsNotNone(build_metric("topic_adherence", {"judge_model": DEEPEVAL_JUDGE_MODEL, "allowed_topics": ["support"]}, []))


if __name__ == "__main__":
    unittest.main()
