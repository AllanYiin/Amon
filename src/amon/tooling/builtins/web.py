"""Web builtin tools."""

from __future__ import annotations

from dataclasses import dataclass
from fnmatch import fnmatch
import json
import os
import re
from typing import Any
from xml.etree import ElementTree
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


@dataclass(frozen=True)
class WebSearchOptions:
    serpapi_api_key_env: str = "SERPAPI_KEY"
    provider_priority: tuple[str, ...] = ("serpapi", "google", "bing")
    max_results_limit: int = 10


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


def spec_web_better_search() -> ToolSpec:
    return ToolSpec(
        name="web.better_search",
        description="Generate multiple search strategies then combine web results.",
        input_schema={
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "max_results": {"type": "integer", "minimum": 1, "maximum": 20, "default": 8},
            },
            "required": ["query"],
            "additionalProperties": False,
        },
        risk="medium",
        annotations={"builtin": True},
    )


def handle_web_search(call: ToolCall, *, policy: WebPolicy, options: WebSearchOptions) -> ToolResult:
    query = call.args.get("query")
    if not isinstance(query, str) or not query:
        return ToolResult(
            content=[{"type": "text", "text": "缺少 query 參數。"}],
            is_error=True,
            meta={"status": "invalid_args"},
        )
    max_results = min(int(call.args.get("max_results", 5)), options.max_results_limit)
    payload, source = _search_with_priority(query, max_results=max_results, policy=policy, options=options)
    if not payload:
        return ToolResult(
            content=[{"type": "text", "text": "查無搜尋結果。"}],
            is_error=True,
            meta={"status": "empty", "provider": source},
        )
    return ToolResult(
        content=[{"type": "text", "text": json.dumps(payload, ensure_ascii=False)}],
        meta={"count": len(payload), "provider": source},
    )


def handle_web_better_search(call: ToolCall, *, policy: WebPolicy, options: WebSearchOptions) -> ToolResult:
    query = call.args.get("query")
    if not isinstance(query, str) or not query.strip():
        return ToolResult(
            content=[{"type": "text", "text": "缺少 query 參數。"}],
            is_error=True,
            meta={"status": "invalid_args"},
        )
    max_results = min(int(call.args.get("max_results", 8)), 20)
    strategies = _build_better_search_queries(query)
    merged: list[dict[str, str]] = []
    seen: set[str] = set()
    providers: list[str] = []
    per_query_limit = max(3, max_results // max(1, len(strategies)))
    for strategy_query in strategies:
        results, provider = _search_with_priority(
            strategy_query,
            max_results=per_query_limit,
            policy=policy,
            options=options,
        )
        providers.append(provider)
        for item in results:
            url = str(item.get("url") or "")
            if not url or url in seen:
                continue
            seen.add(url)
            item = {"title": str(item.get("title") or ""), "url": url, "strategy_query": strategy_query}
            merged.append(item)
            if len(merged) >= max_results:
                break
        if len(merged) >= max_results:
            break
    if not merged:
        return ToolResult(
            content=[{"type": "text", "text": "查無搜尋結果。"}],
            is_error=True,
            meta={"status": "empty", "providers": providers, "strategies": strategies},
        )
    return ToolResult(
        content=[{"type": "text", "text": json.dumps(merged, ensure_ascii=False)}],
        meta={"count": len(merged), "providers": providers, "strategies": strategies},
    )


def register_web_tools(registry: Any, *, policy: WebPolicy, options: WebSearchOptions | None = None) -> None:
    search_options = options or WebSearchOptions()
    registry.register(spec_web_fetch(), lambda call: handle_web_fetch(call, policy=policy))
    registry.register(spec_web_search(), lambda call: handle_web_search(call, policy=policy, options=search_options))
    registry.register(
        spec_web_better_search(),
        lambda call: handle_web_better_search(call, policy=policy, options=search_options),
    )


def _parse_duckduckgo(html_text: str) -> list[dict[str, str]]:
    results: list[dict[str, str]] = []
    pattern = re.compile(r"<a[^>]+class=\"result__a\"[^>]+href=\"(?P<link>[^\"]+)\"[^>]*>(?P<title>.*?)</a>")
    for match in pattern.finditer(html_text):
        title = re.sub(r"<.*?>", "", match.group("title"))
        link = match.group("link")
        results.append({"title": title, "url": link})
    return results


def _search_with_priority(query: str, *, max_results: int, policy: WebPolicy, options: WebSearchOptions) -> tuple[list[dict[str, str]], str]:
    for provider in options.provider_priority:
        provider_name = str(provider).strip().lower()
        if provider_name == "serpapi":
            matches, status = _search_with_serpapi(query, max_results=max_results, policy=policy, options=options)
        elif provider_name == "google":
            matches, status = _search_with_google_builtin(query, max_results=max_results, policy=policy)
        elif provider_name == "bing":
            matches, status = _search_with_bing_builtin(query, max_results=max_results, policy=policy)
        else:
            continue
        if matches:
            return matches, provider_name
        if status in {"quota_exceeded", "missing_key", "service_unavailable", "empty"}:
            continue
    return [], "none"


def _search_with_serpapi(query: str, *, max_results: int, policy: WebPolicy, options: WebSearchOptions) -> tuple[list[dict[str, str]], str]:
    api_key = os.environ.get(options.serpapi_api_key_env, "").strip()
    if not api_key:
        return [], "missing_key"
    url = "https://serpapi.com/search.json?" + parse.urlencode(
        {"engine": "google", "q": query, "num": max_results, "api_key": api_key}
    )
    fetch_result = handle_web_fetch(ToolCall(tool="web.fetch", args={"url": url, "method": "GET"}), policy=policy)
    if fetch_result.is_error:
        return [], "service_unavailable"
    try:
        payload = json.loads(fetch_result.as_text())
    except json.JSONDecodeError:
        return [], "bad_payload"
    error_text = str(payload.get("error") or "").lower() if isinstance(payload, dict) else ""
    if "limit" in error_text or "quota" in error_text:
        return [], "quota_exceeded"
    organic = payload.get("organic_results", []) if isinstance(payload, dict) else []
    results: list[dict[str, str]] = []
    for item in organic[:max_results]:
        if not isinstance(item, dict):
            continue
        title = str(item.get("title") or "").strip()
        link = str(item.get("link") or "").strip()
        if not title or not link:
            continue
        results.append({"title": title, "url": link})
    return results, "ok"


def _search_with_google_builtin(query: str, *, max_results: int, policy: WebPolicy) -> tuple[list[dict[str, str]], str]:
    rss_url = "https://news.google.com/rss/search?" + parse.urlencode({"q": query, "hl": "zh-TW", "gl": "TW", "ceid": "TW:zh-Hant"})
    fetch_result = handle_web_fetch(ToolCall(tool="web.fetch", args={"url": rss_url, "method": "GET"}), policy=policy)
    if fetch_result.is_error:
        return [], "service_unavailable"
    try:
        root = ElementTree.fromstring(fetch_result.as_text())
    except ElementTree.ParseError:
        return [], "bad_payload"
    results: list[dict[str, str]] = []
    for item in root.findall("./channel/item")[:max_results]:
        title = (item.findtext("title") or "").strip()
        link = (item.findtext("link") or "").strip()
        if title and link:
            results.append({"title": title, "url": link})
    return results, "ok" if results else "empty"


def _search_with_bing_builtin(query: str, *, max_results: int, policy: WebPolicy) -> tuple[list[dict[str, str]], str]:
    url = "https://www.bing.com/search?" + parse.urlencode({"q": query})
    fetch_result = handle_web_fetch(
        ToolCall(
            tool="web.fetch",
            args={
                "url": url,
                "method": "GET",
                "headers": {"User-Agent": "Mozilla/5.0 Amon/1.0"},
            },
        ),
        policy=policy,
    )
    if fetch_result.is_error:
        return [], "service_unavailable"
    html_text = fetch_result.as_text()
    pattern = re.compile(
        r'<li class="b_algo".*?<h2><a href="(?P<link>[^"]+)"[^>]*>(?P<title>.*?)</a>',
        re.S,
    )
    results: list[dict[str, str]] = []
    for match in pattern.finditer(html_text):
        title = re.sub(r"<.*?>", "", match.group("title")).strip()
        link = (match.group("link") or "").strip()
        if not title or not link:
            continue
        results.append({"title": title, "url": link})
        if len(results) >= max_results:
            break
    return results, "ok" if results else "empty"


def _build_better_search_queries(query: str) -> list[str]:
    normalized = " ".join(str(query).split())
    variants = [
        normalized,
        f"{normalized} 最新",
        f"{normalized} 教學",
        f"{normalized} 比較",
    ]
    deduped: list[str] = []
    for item in variants:
        if item and item not in deduped:
            deduped.append(item)
    return deduped
