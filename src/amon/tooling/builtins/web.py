"""Web builtin tools."""

from __future__ import annotations

from dataclasses import dataclass
from fnmatch import fnmatch
import json
import re
from typing import Any
from urllib import parse, request

from ..types import ToolCall, ToolResult, ToolSpec


@dataclass(frozen=True)
class WebPolicy:
    allowlist: tuple[str, ...] = ()
    denylist: tuple[str, ...] = ()

    def is_allowed(self, url: str) -> bool:
        parsed = parse.urlparse(url)
        host = parsed.netloc
        if self.denylist and any(fnmatch(host, pattern) for pattern in self.denylist):
            return False
        if not self.allowlist:
            return True
        return any(fnmatch(host, pattern) for pattern in self.allowlist)


def spec_web_fetch() -> ToolSpec:
    return ToolSpec(
        name="web.fetch",
        description="Fetch a URL and return the response text.",
        input_schema={
            "type": "object",
            "properties": {
                "url": {"type": "string"},
                "method": {"type": "string", "default": "GET"},
                "headers": {"type": "object"},
                "timeout": {"type": "number", "default": 10},
                "max_bytes": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 5_000_000,
                    "default": 200_000,
                },
            },
            "required": ["url"],
            "additionalProperties": False,
        },
        risk="medium",
        annotations={"builtin": True},
    )


def handle_web_fetch(call: ToolCall, *, policy: WebPolicy) -> ToolResult:
    url = call.args.get("url")
    if not isinstance(url, str) or not url:
        return ToolResult(
            content=[{"type": "text", "text": "缺少 url 參數。"}],
            is_error=True,
            meta={"status": "invalid_args"},
        )
    if not policy.is_allowed(url):
        return ToolResult(
            content=[{"type": "text", "text": "網址不在允許清單內。"}],
            is_error=True,
            meta={"status": "not_allowed"},
        )
    method = str(call.args.get("method", "GET")).upper()
    headers = call.args.get("headers")
    if headers is not None and not isinstance(headers, dict):
        return ToolResult(
            content=[{"type": "text", "text": "headers 參數必須是物件。"}],
            is_error=True,
            meta={"status": "invalid_args"},
        )
    timeout = float(call.args.get("timeout", 10))
    max_bytes = int(call.args.get("max_bytes", 200_000))
    req = request.Request(url=url, method=method)
    if isinstance(headers, dict):
        for key, value in headers.items():
            if value is None:
                continue
            req.add_header(str(key), str(value))
    try:
        with request.urlopen(req, timeout=timeout) as resp:
            data = resp.read(max_bytes + 1)
            truncated = len(data) > max_bytes
            if truncated:
                data = data[:max_bytes]
            text = data.decode("utf-8", errors="replace")
            status = getattr(resp, "status", 200)
    except Exception as exc:  # noqa: BLE001 - keep surface simple
        return ToolResult(
            content=[{"type": "text", "text": f"請求失敗：{exc}"}],
            is_error=True,
            meta={"status": "request_failed"},
        )
    return ToolResult(
        content=[{"type": "text", "text": text}],
        meta={"status": status, "truncated": truncated},
    )


def spec_web_search() -> ToolSpec:
    return ToolSpec(
        name="web.search",
        description="Search the web and return top results.",
        input_schema={
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "max_results": {"type": "integer", "minimum": 1, "maximum": 10, "default": 5},
            },
            "required": ["query"],
            "additionalProperties": False,
        },
        risk="medium",
        annotations={"builtin": True},
    )


def handle_web_search(call: ToolCall, *, policy: WebPolicy) -> ToolResult:
    query = call.args.get("query")
    if not isinstance(query, str) or not query:
        return ToolResult(
            content=[{"type": "text", "text": "缺少 query 參數。"}],
            is_error=True,
            meta={"status": "invalid_args"},
        )
    max_results = int(call.args.get("max_results", 5))
    url = "https://duckduckgo.com/html/?" + parse.urlencode({"q": query})
    fetch_result = handle_web_fetch(
        ToolCall(tool="web.fetch", args={"url": url, "method": "GET"}),
        policy=policy,
    )
    if fetch_result.is_error:
        return fetch_result
    matches = _parse_duckduckgo(fetch_result.as_text())
    payload = matches[:max_results]
    return ToolResult(
        content=[{"type": "text", "text": json.dumps(payload, ensure_ascii=False)}],
        meta={"count": len(payload)},
    )


def register_web_tools(registry: Any, *, policy: WebPolicy) -> None:
    registry.register(spec_web_fetch(), lambda call: handle_web_fetch(call, policy=policy))
    registry.register(spec_web_search(), lambda call: handle_web_search(call, policy=policy))


def _parse_duckduckgo(html_text: str) -> list[dict[str, str]]:
    results: list[dict[str, str]] = []
    pattern = re.compile(r"<a[^>]+class=\"result__a\"[^>]+href=\"(?P<link>[^\"]+)\"[^>]*>(?P<title>.*?)</a>")
    for match in pattern.finditer(html_text):
        title = re.sub(r"<.*?>", "", match.group("title"))
        link = match.group("link")
        results.append({"title": title, "url": link})
    return results
