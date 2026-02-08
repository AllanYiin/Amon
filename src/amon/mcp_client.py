"""MCP client helpers (stdio transport)."""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any


class MCPClientError(RuntimeError):
    """Raised when MCP communication fails."""


@dataclass
class MCPServerConfig:
    name: str
    transport: str
    command: list[str] | None = None
    url: str | None = None
    allowed: list[str] | None = None


class MCPStdioClient:
    def __init__(self, command: list[str], cwd: Path | None = None) -> None:
        self._command = command
        self._cwd = cwd
        self._process: subprocess.Popen[str] | None = None
        self._request_id = 0

    def __enter__(self) -> MCPStdioClient:
        self.start()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    def start(self) -> None:
        if self._process:
            return
        try:
            self._process = subprocess.Popen(
                self._command,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                cwd=self._cwd,
                bufsize=1,
            )
        except OSError as exc:
            raise MCPClientError(f"啟動 MCP server 失敗：{exc}") from exc

    def close(self) -> None:
        if not self._process:
            return
        if self._process.stdin:
            self._process.stdin.close()
        self._process.terminate()
        try:
            self._process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            self._process.kill()
        if self._process.stdout:
            self._process.stdout.close()
        if self._process.stderr:
            self._process.stderr.close()
        self._process = None

    def list_tools(self) -> list[dict[str, Any]]:
        response = self._request("tools/list", {})
        result = response.get("result", {})
        return result.get("tools", [])

    def call_tool(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        response = self._request("tools/call", {"name": name, "arguments": arguments})
        return response.get("result", {})

    def _request(self, method: str, params: dict[str, Any]) -> dict[str, Any]:
        if not self._process or not self._process.stdin or not self._process.stdout:
            raise MCPClientError("MCP server 尚未啟動")
        self._request_id += 1
        payload = {"jsonrpc": "2.0", "id": self._request_id, "method": method, "params": params}
        try:
            self._process.stdin.write(json.dumps(payload, ensure_ascii=False))
            self._process.stdin.write("\n")
            self._process.stdin.flush()
        except OSError as exc:
            raise MCPClientError(f"送出 MCP 請求失敗：{exc}") from exc
        try:
            line = self._process.stdout.readline()
        except OSError as exc:
            raise MCPClientError(f"讀取 MCP 回應失敗：{exc}") from exc
        if not line:
            stderr = ""
            if self._process.poll() is not None and self._process.stderr:
                stderr = self._process.stderr.read().strip()
            raise MCPClientError(f"MCP server 無回應：{stderr or 'stdout empty'}")
        try:
            response = json.loads(line)
        except json.JSONDecodeError as exc:
            raise MCPClientError(f"MCP 回應格式錯誤：{line}") from exc
        if "error" in response:
            raise MCPClientError(f"MCP 回應錯誤：{response['error']}")
        return response
