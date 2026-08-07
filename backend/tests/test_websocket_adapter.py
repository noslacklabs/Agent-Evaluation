from __future__ import annotations

import json
import unittest

import websockets

from adapters.websocket import WebSocketAdapter


class WebSocketAdapterTests(unittest.IsolatedAsyncioTestCase):
    async def test_single_json_response_is_normalized(self):
        async def handler(socket):
            request = json.loads(await socket.recv())
            await socket.send(json.dumps({
                "output": f"Echo: {request['input']}",
                "retrieval_context": ["demo context"],
                "tools_called": [{"name": "demo_tool"}],
            }))

        async with websockets.serve(handler, "127.0.0.1", 0) as server:
            port = server.sockets[0].getsockname()[1]
            adapter = WebSocketAdapter(
                {
                    "websocket_url": f"ws://127.0.0.1:{port}",
                    "allow_private_network": True,
                    "response_mapping": {
                        "output": "output",
                        "retrieval_context": "retrieval_context",
                        "tools_called": "tools_called",
                    },
                },
                {},
            )
            response = await adapter.invoke("hello")

        self.assertEqual(response.output, "Echo: hello")
        self.assertEqual(response.retrieval_context, ["demo context"])
        self.assertEqual(response.tools_called, [{"name": "demo_tool"}])

    async def test_stream_frames_are_combined_until_done_event(self):
        async def handler(socket):
            await socket.recv()
            await socket.send(json.dumps({"type": "chunk", "output": "Hello "}))
            await socket.send(json.dumps({"type": "chunk", "output": "world"}))
            await socket.send(json.dumps({"type": "done"}))

        async with websockets.serve(handler, "127.0.0.1", 0) as server:
            port = server.sockets[0].getsockname()[1]
            adapter = WebSocketAdapter(
                {
                    "websocket_url": f"ws://127.0.0.1:{port}",
                    "allow_private_network": True,
                    "response_mode": "stream",
                    "done_path": "type",
                    "done_value": "done",
                    "response_mapping": {"output": "output"},
                },
                {},
            )
            response = await adapter.invoke("hello")

        self.assertEqual(response.output, "Hello world")
        self.assertEqual(response.metadata["websocket_frames"], 2)
