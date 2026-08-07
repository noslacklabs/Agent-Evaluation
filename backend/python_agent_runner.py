from __future__ import annotations

import asyncio
import importlib
import inspect
import json
import sys
from pathlib import Path


def main() -> None:
    package_path, entrypoint = sys.argv[1], sys.argv[2]
    source = Path(package_path).resolve()
    sys.path.insert(0, str(source))
    module_name, function_name = entrypoint.split(":", 1)
    function = getattr(importlib.import_module(module_name), function_name)
    payload = json.loads(sys.stdin.read())
    signature = inspect.signature(function)
    if len(signature.parameters) == 1:
        result = function(payload)
    else:
        result = function(**payload)
    if inspect.isawaitable(result):
        result = asyncio.run(result)
    if isinstance(result, str):
        result = {"output": result}
    sys.stdout.write(json.dumps(result, default=str))


if __name__ == "__main__":
    main()

