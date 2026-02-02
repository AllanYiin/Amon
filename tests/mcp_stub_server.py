"""Minimal MCP stdio stub server for tests."""

from __future__ import annotations

import json
import sys


def main() -> None:
    for line in sys.stdin:
        if not line.strip():
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        method = payload.get("method")
        request_id = payload.get("id")
        if method == "tools/list":
            result = {
                "tools": [
                    {
                        "name": "echo",
                        "description": "Echo input arguments",
                        "inputSchema": {"type": "object", "properties": {"text": {"type": "string"}}},
                    }
                ]
            }
        elif method == "tools/call":
            params = payload.get("params", {})
            result = {"echo": params}
        else:
            result = {}
        response = {"jsonrpc": "2.0", "id": request_id, "result": result}
        sys.stdout.write(json.dumps(response, ensure_ascii=False))
        sys.stdout.write("\n")
        sys.stdout.flush()


if __name__ == "__main__":
    main()
