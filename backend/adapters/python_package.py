from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

from adapters.base import AgentAdapter
from config import PYTHON_AGENT_TIMEOUT_SECONDS, SERVICE_DIR
from schemas import AgentResponse


class PythonPackageAdapter(AgentAdapter):
    async def invoke(self, user_input: str, *, messages=None, session_id=None) -> AgentResponse:
        package_path = self.config.get("package_path")
        entrypoint = self.config.get("entrypoint")
        if not package_path or not Path(package_path).exists():
            raise ValueError("Uploaded Python package is missing")
        if not entrypoint or ":" not in entrypoint:
            raise ValueError("Python entrypoint must use module:function format")
        request = {"input": user_input, "messages": messages or [], "session_id": session_id}
        process = await asyncio.create_subprocess_exec(
            sys.executable,
            str(SERVICE_DIR / "python_agent_runner.py"),
            package_path,
            entrypoint,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout, stderr = await asyncio.wait_for(
                process.communicate(json.dumps(request).encode("utf-8")),
                timeout=float(self.config.get("timeout_seconds", PYTHON_AGENT_TIMEOUT_SECONDS)),
            )
        except asyncio.TimeoutError:
            process.kill()
            await process.wait()
            raise TimeoutError("Python agent invocation timed out")
        if process.returncode != 0:
            raise RuntimeError(stderr.decode("utf-8", errors="replace")[-2000:])
        data = json.loads(stdout.decode("utf-8"))
        if isinstance(data, str):
            return AgentResponse(output=data)
        return AgentResponse.model_validate(data)

