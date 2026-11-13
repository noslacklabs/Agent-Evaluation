from __future__ import annotations

import json
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from adapters import create_adapter
from adapters.langflow import LangflowAdapter, extract_tool_calls

FIXTURES = Path(__file__).parent / "fixtures"


def fixture(name: str) -> dict:
    """A real response from Langflow 1.13.2 `POST /api/v1/run/{flow_id}`."""
    return json.loads((FIXTURES / f"{name}.json").read_text(encoding="utf-8"))


class FakeLangflow:
    """A local HTTP server that answers every run request with one canned reply."""

    def __init__(self, reply: dict | None = None, status: int = 200):
        self.requests: list[dict] = []
        outer = self

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):  # noqa: N802
                length = int(self.headers.get("Content-Length", 0))
                outer.requests.append({
                    "path": self.path,
                    "api_key": self.headers.get("x-api-key"),
                    "body": json.loads(self.rfile.read(length) or b"{}"),
                })
                payload = json.dumps(reply if reply is not None else {}).encode()
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)

            def log_message(self, *args):
                pass

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.url = f"http://127.0.0.1:{self.server.server_address[1]}"
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)

    def __enter__(self):
        self.thread.start()
        return self

    def __exit__(self, *exc):
        self.server.shutdown()
        self.server.server_close()

    def adapter(self, **config) -> LangflowAdapter:
        base = {"base_url": self.url, "flow_id": "flow-1", "allow_private_network": True}
        return LangflowAdapter({**base, **config}, {"api_key": "lf-test-key"})


class LangflowAdapterTests(unittest.IsolatedAsyncioTestCase):
    async def test_sends_api_key_session_and_chat_types(self):
        with FakeLangflow(fixture("langflow_run_single_agent")) as langflow:
            await langflow.adapter().invoke("hello", session_id="run-7:3")
        request = langflow.requests[0]
        self.assertEqual(request["path"], "/api/v1/run/flow-1?stream=false")
        self.assertEqual(request["api_key"], "lf-test-key")
        self.assertEqual(
            request["body"],
            {"input_value": "hello", "input_type": "chat", "output_type": "chat", "session_id": "run-7:3"},
        )

    async def test_each_call_without_a_session_gets_its_own(self):
        with FakeLangflow(fixture("langflow_run_single_agent")) as langflow:
            adapter = langflow.adapter()
            await adapter.invoke("one")
            await adapter.invoke("two")
            await adapter.test_connection("three")
            await adapter.test_connection("four")
        sessions = [request["body"]["session_id"] for request in langflow.requests]
        self.assertEqual(len(set(sessions)), 4)
        self.assertTrue(all(sessions))

    async def test_single_agent_answer_tools_and_usage(self):
        with FakeLangflow(fixture("langflow_run_single_agent")) as langflow:
            response = await langflow.adapter().invoke("use get_current_date please")
        self.assertTrue(response.output.startswith("Final answer:"))
        self.assertEqual([call["name"] for call in response.tools_called], ["get_current_date"])
        self.assertIn("timezone", response.tools_called[0]["input_parameters"])
        self.assertIsInstance(response.tools_called[0]["output"], str)  # the tool's result, not a wrapper
        self.assertGreater(response.usage["total_tokens"], 0)
        self.assertEqual(response.metadata["status_code"], 200)

    async def test_supervisor_lists_the_agent_then_the_tools_it_used(self):
        with FakeLangflow(fixture("langflow_run_supervisor")) as langflow:
            response = await langflow.adapter().invoke("ask the Analyst")
        calls = [(call.get("agent"), call["name"], call.get("is_agent", False)) for call in response.tools_called]
        self.assertEqual(calls, [(None, "Analyst", True), ("Analyst", "evaluate_expression", False)])
        # The agent entry carries the agent's answer, not the whole report.
        self.assertIsInstance(response.tools_called[0]["output"], str)

    async def test_solo_agent_run_lists_only_that_agents_tools(self):
        tweaks = {"orchestrator-block-id": {"solo_agent": "Researcher"}}
        with FakeLangflow(fixture("langflow_run_solo_agent")) as langflow:
            adapter = langflow.adapter(tweaks=tweaks, solo_agent="Researcher", include_agent_calls=False)
            response = await adapter.invoke("use get_current_date")
        self.assertEqual(langflow.requests[0]["body"]["tweaks"], tweaks)
        self.assertEqual([(c["agent"], c["name"]) for c in response.tools_called], [("Researcher", "get_current_date")])

    async def test_solo_registration_is_rejected_when_the_flow_ran_its_normal_pattern(self):
        # The tweak no longer reaches the Orchestrator block (it was replaced), so Langflow ran the
        # whole supervisor flow. Scoring that under one agent's name would be wrong.
        with FakeLangflow(fixture("langflow_run_supervisor")) as langflow:
            adapter = langflow.adapter(tweaks={"gone-block": {"solo_agent": "Analyst"}}, solo_agent="Analyst")
            with self.assertRaisesRegex(ValueError, "did not run agent 'Analyst' on its own"):
                await adapter.invoke("ask the Analyst")

    async def test_solo_registration_is_rejected_when_a_different_agent_ran(self):
        with FakeLangflow(fixture("langflow_run_solo_agent")) as langflow:
            adapter = langflow.adapter(solo_agent="Writer")
            with self.assertRaisesRegex(ValueError, "did not run agent 'Writer' on its own"):
                await adapter.invoke("hi")

    async def test_retrieval_context_from_named_tools(self):
        with FakeLangflow(fixture("langflow_run_single_agent")) as langflow:
            response = await langflow.adapter(retrieval_tools=["get_current_date"]).invoke("hi")
        self.assertEqual(len(response.retrieval_context), 1)
        self.assertEqual(response.retrieval_context[0], response.tools_called[0]["output"])

    async def test_retrieval_context_from_a_second_output(self):
        reply = {"outputs": [{"outputs": [
            {"component_id": "ChatOutput-ctx", "component_display_name": "Retrieved Chunks",
             "results": {"message": {"text": "chunk about refunds"}}},
            {"component_id": "ChatOutput-ans", "component_display_name": "Chat Output",
             "results": {"message": {"text": "Refunds take 5 days.", "content_blocks": []}}},
        ]}]}
        with FakeLangflow(reply) as langflow:
            response = await langflow.adapter(retrieval_output_component="Retrieved Chunks").invoke("refunds?")
        self.assertEqual(response.output, "Refunds take 5 days.")
        self.assertEqual(response.retrieval_context, ["chunk about refunds"])

    async def test_answer_is_found_when_it_is_not_the_first_output(self):
        reply = {"outputs": [{"outputs": [
            {"component_id": "TextOutput-1", "results": {"text": {"text": "not a chat message"}}},
            {"component_id": "ChatOutput-2", "results": {"message": {"text": "the answer"}}},
        ]}]}
        with FakeLangflow(reply) as langflow:
            self.assertEqual((await langflow.adapter().invoke("q")).output, "the answer")
            self.assertEqual((await langflow.adapter(output_component="ChatOutput-2").invoke("q")).output, "the answer")
            with self.assertRaisesRegex(ValueError, "no output from component 'Missing'"):
                await langflow.adapter(output_component="Missing").invoke("q")

    async def test_refused_key_and_run_errors_are_explained(self):
        with FakeLangflow({"detail": "nope"}, status=403) as langflow:
            with self.assertRaisesRegex(ValueError, "Check the Langflow API key"):
                await langflow.adapter().invoke("q")
        detail = json.dumps({"message": "Error running graph: Blocked by guardrail: bad word"})
        with FakeLangflow({"detail": detail}, status=500) as langflow:
            with self.assertRaisesRegex(ValueError, "Blocked by guardrail"):
                await langflow.adapter().invoke("q")
        with FakeLangflow({"outputs": []}) as langflow:
            with self.assertRaisesRegex(ValueError, "no chat message"):
                await langflow.adapter().invoke("q")

    async def test_local_endpoint_needs_the_private_network_flag(self):
        adapter = LangflowAdapter({"base_url": "http://127.0.0.1:7860", "flow_id": "f"}, {})
        with self.assertRaisesRegex(ValueError, "allow_private_network"):
            await adapter.invoke("q")

    async def test_both_connection_types_use_this_adapter(self):
        with FakeLangflow(fixture("langflow_run_supervisor")) as langflow:
            config = {"base_url": langflow.url, "flow_id": "flow-1", "allow_private_network": True}
            secrets = {"api_key": "lf-test-key"}
            direct = await create_adapter("langflow", config, secrets).invoke("q", session_id="s")
            preset = await create_adapter("framework", {**config, "preset": "langflow"}, secrets).invoke(
                "q", session_id="s"
            )
        # The old preset now authenticates and reports tool calls too.
        self.assertEqual([request["api_key"] for request in langflow.requests], ["lf-test-key", "lf-test-key"])
        self.assertEqual(direct.tools_called, preset.tools_called)
        self.assertEqual(len(preset.tools_called), 2)


class ExtractToolCallsTests(unittest.TestCase):
    def test_flat_and_nested_layouts(self):
        block = {"type": "tool_use", "name": "search", "tool_input": {"q": "x"}, "output": "found"}
        expected = [{"name": "search", "input_parameters": {"q": "x"}, "output": "found"}]
        self.assertEqual(extract_tool_calls([block]), expected)
        self.assertEqual(extract_tool_calls([{"title": "Agent Steps", "contents": [block, {"type": "text"}]}]), expected)
        self.assertEqual(extract_tool_calls(None), [])


if __name__ == "__main__":
    unittest.main()
