from __future__ import annotations

import unittest

from adapters.utils import extract_openai_response, get_path, render_template


class AdapterUtilsTests(unittest.TestCase):
    def test_dot_path_and_template(self):
        values = {"input": "hello", "messages": [{"role": "user", "content": "hello"}]}
        payload = render_template({"query": "{{input}}", "messages": "{{messages}}"}, values)
        self.assertEqual(payload["query"], "hello")
        self.assertIsInstance(payload["messages"], list)
        self.assertEqual(get_path({"a": [{"b": 2}]}, "a.0.b"), 2)

    def test_openai_chat_and_responses_output(self):
        self.assertEqual(extract_openai_response({"choices": [{"message": {"content": "chat"}}]}), "chat")
        data = {"output": [{"content": [{"type": "output_text", "text": "response"}]}]}
        self.assertEqual(extract_openai_response(data), "response")


if __name__ == "__main__":
    unittest.main()

