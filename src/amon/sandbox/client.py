"""HTTP client for external sandbox runner integration."""

from __future__ import annotations

import base64
import json
import os
import socket
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping
from urllib import error, parse, request

from .path_rules import validate_relative_path


class SandboxClientError(RuntimeError):
    """Base error for sandbox runner client failures."""


class SandboxTimeoutError(SandboxClientError):
    """Raised when sandbox runner request times out."""


class SandboxHTTPError(SandboxClientError):
    """Raised when sandbox runner returns non-2xx status."""


class SandboxProtocolError(SandboxClientError):
    """Raised when sandbox runner response schema is invalid."""


@dataclass(frozen=True)
class SandboxRunnerSettings:
    base_url: str
    timeout_s: int
    api_key_env: str | None
    limits: Mapping[str, Any]
    features: Mapping[str, Any]


def parse_runner_settings(config: Mapping[str, Any]) -> SandboxRunnerSettings:
    sandbox = config.get("sandbox", {}) if isinstance(config, Mapping) else {}
    runner = sandbox.get("runner", {}) if isinstance(sandbox, Mapping) else {}
    if not isinstance(runner, Mapping):
        runner = {}

    return SandboxRunnerSettings(
        base_url=str(runner.get("base_url", "http://127.0.0.1:8088")),
        timeout_s=int(runner.get("timeout_s", 30)),
        api_key_env=runner.get("api_key_env") or None,
        limits=runner.get("limits", {}) if isinstance(runner.get("limits", {}), Mapping) else {},
        features=runner.get("features", {}) if isinstance(runner.get("features", {}), Mapping) else {},
    )


def build_input_file(path: str, content: bytes) -> dict[str, Any]:
    return {"path": validate_relative_path(path), "content_b64": base64.b64encode(content).decode("ascii")}


class SandboxRunnerClient:
    def __init__(self, settings: SandboxRunnerSettings) -> None:
        self._settings = settings

    def run_code(
        self,
        *,
        language: str,
        code: str,
        timeout_s: int | None = None,
        input_files: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        payload = {
            "language": language,
            "code": code,
            "timeout_s": timeout_s or self._settings.timeout_s,
            "input_files": input_files or [],
        }

        body = json.dumps(payload).encode("utf-8")
        endpoint = parse.urljoin(self._settings.base_url.rstrip("/") + "/", "run")
        headers = {"Content-Type": "application/json"}

        token = _resolve_api_key(self._settings.api_key_env)
        if token:
            headers["Authorization"] = f"Bearer {token}"

        req = request.Request(endpoint, data=body, headers=headers, method="POST")

        try:
            with request.urlopen(req, timeout=self._settings.timeout_s) as response:
                raw = response.read().decode("utf-8")
        except error.HTTPError as exc:
            detail = _safe_error_body(exc)
            raise SandboxHTTPError(f"runner 回傳 HTTP {exc.code}：{detail}") from exc
        except (socket.timeout, TimeoutError) as exc:
            raise SandboxTimeoutError("呼叫 sandbox runner 逾時") from exc
        except error.URLError as exc:
            if isinstance(exc.reason, TimeoutError):
                raise SandboxTimeoutError("呼叫 sandbox runner 逾時") from exc
            raise SandboxClientError(f"無法連線 sandbox runner：{exc.reason}") from exc

        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise SandboxProtocolError("runner 回傳非合法 JSON") from exc

        if not isinstance(parsed, dict):
            raise SandboxProtocolError("runner 回應格式錯誤：必須是 JSON object")

        if not isinstance(parsed.get("output_files", []), list):
            raise SandboxProtocolError("runner 回應格式錯誤：output_files 必須為 list")

        return parsed


def decode_output_files(output_files: list[dict[str, Any]], out_dir: Path) -> list[Path]:
    out_dir = out_dir.resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []

    for item in output_files:
        if not isinstance(item, dict):
            raise SandboxProtocolError("output_files 項目格式錯誤")

        try:
            rel_path = validate_relative_path(str(item.get("path", "")))
        except ValueError as exc:
            raise SandboxProtocolError("output_files.path 格式錯誤") from exc
        raw_content = item.get("content_b64")
        if not isinstance(raw_content, str):
            raise SandboxProtocolError("output_files.content_b64 格式錯誤")

        try:
            content = base64.b64decode(raw_content, validate=True)
        except (ValueError, TypeError) as exc:
            raise SandboxProtocolError(f"output file base64 格式錯誤：{rel_path}") from exc

        target = (out_dir / rel_path).resolve()
        if out_dir not in target.parents and target != out_dir:
            raise SandboxProtocolError(f"output file path 非法：{rel_path}")

        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
        written.append(target)

    return written


def _resolve_api_key(api_key_env: str | None) -> str | None:
    if not api_key_env:
        return None
    return os.environ.get(api_key_env)


def _safe_error_body(exc: error.HTTPError) -> str:
    try:
        raw = exc.read().decode("utf-8")
        parsed = json.loads(raw)
        if isinstance(parsed, dict) and isinstance(parsed.get("detail"), str):
            return parsed["detail"]
        return raw[:200]
    except Exception:  # noqa: BLE001
        return "runner 回傳錯誤"
