"""Memory builtin tools."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any

from ..types import ToolCall, ToolResult, ToolSpec


@dataclass(frozen=True)
class MemoryStore:
    base_dir: Path

    def _namespace_dir(self, namespace: str) -> Path:
        safe_namespace = namespace.replace("/", "_")
        return self.base_dir / safe_namespace

    def put(self, namespace: str, key: str, value: Any) -> Path:
        directory = self._namespace_dir(namespace)
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / f"{key}.json"
        with path.open("w", encoding="utf-8") as handle:
            json.dump({"key": key, "value": value}, handle, ensure_ascii=False)
        return path

    def get(self, namespace: str, key: str) -> Any:
        path = self._namespace_dir(namespace) / f"{key}.json"
        with path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
        return data.get("value")

    def delete(self, namespace: str, key: str) -> None:
        path = self._namespace_dir(namespace) / f"{key}.json"
        path.unlink()

    def search(self, namespace: str, query: str) -> list[dict[str, Any]]:
        directory = self._namespace_dir(namespace)
        if not directory.exists():
            return []
        results: list[dict[str, Any]] = []
        for path in directory.glob("*.json"):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if query in json.dumps(data, ensure_ascii=False):
                results.append({"key": data.get("key"), "value": data.get("value")})
        return results


def spec_memory_put() -> ToolSpec:
    return ToolSpec(
        name="memory.put",
        description="Store a JSON-serializable value under a key.",
        input_schema={
            "type": "object",
            "properties": {
                "namespace": {"type": "string", "default": "default"},
                "key": {"type": "string"},
                "value": {},
            },
            "required": ["key", "value"],
            "additionalProperties": False,
        },
        risk="low",
        annotations={"builtin": True},
    )


def handle_memory_put(call: ToolCall, *, store: MemoryStore) -> ToolResult:
    namespace = str(call.args.get("namespace", "default"))
    key = call.args.get("key")
    if not isinstance(key, str) or not key:
        return ToolResult(
            content=[{"type": "text", "text": "缺少 key 參數。"}],
            is_error=True,
            meta={"status": "invalid_args"},
        )
    value = call.args.get("value")
    try:
        path = store.put(namespace, key, value)
    except OSError as exc:
        return ToolResult(
            content=[{"type": "text", "text": f"寫入記憶失敗：{exc}"}],
            is_error=True,
            meta={"status": "io_error"},
        )
    except TypeError as exc:
        return ToolResult(
            content=[{"type": "text", "text": f"內容不可序列化：{exc}"}],
            is_error=True,
            meta={"status": "invalid_value"},
        )
    return ToolResult(content=[{"type": "text", "text": f"已儲存：{path}"}])


def spec_memory_get() -> ToolSpec:
    return ToolSpec(
        name="memory.get",
        description="Retrieve a stored value by key.",
        input_schema={
            "type": "object",
            "properties": {
                "namespace": {"type": "string", "default": "default"},
                "key": {"type": "string"},
            },
            "required": ["key"],
            "additionalProperties": False,
        },
        risk="low",
        annotations={"builtin": True},
    )


def handle_memory_get(call: ToolCall, *, store: MemoryStore) -> ToolResult:
    namespace = str(call.args.get("namespace", "default"))
    key = call.args.get("key")
    if not isinstance(key, str) or not key:
        return ToolResult(
            content=[{"type": "text", "text": "缺少 key 參數。"}],
            is_error=True,
            meta={"status": "invalid_args"},
        )
    try:
        value = store.get(namespace, key)
    except FileNotFoundError:
        return ToolResult(
            content=[{"type": "text", "text": "找不到記錄。"}],
            is_error=True,
            meta={"status": "not_found"},
        )
    except OSError as exc:
        return ToolResult(
            content=[{"type": "text", "text": f"讀取記憶失敗：{exc}"}],
            is_error=True,
            meta={"status": "io_error"},
        )
    return ToolResult(
        content=[{"type": "text", "text": json.dumps(value, ensure_ascii=False)}],
        meta={"namespace": namespace, "key": key},
    )


def spec_memory_search() -> ToolSpec:
    return ToolSpec(
        name="memory.search",
        description="Search stored values by substring.",
        input_schema={
            "type": "object",
            "properties": {
                "namespace": {"type": "string", "default": "default"},
                "query": {"type": "string"},
            },
            "required": ["query"],
            "additionalProperties": False,
        },
        risk="low",
        annotations={"builtin": True},
    )


def handle_memory_search(call: ToolCall, *, store: MemoryStore) -> ToolResult:
    namespace = str(call.args.get("namespace", "default"))
    query = call.args.get("query")
    if not isinstance(query, str) or not query:
        return ToolResult(
            content=[{"type": "text", "text": "缺少 query 參數。"}],
            is_error=True,
            meta={"status": "invalid_args"},
        )
    try:
        results = store.search(namespace, query)
    except OSError as exc:
        return ToolResult(
            content=[{"type": "text", "text": f"搜尋記憶失敗：{exc}"}],
            is_error=True,
            meta={"status": "io_error"},
        )
    return ToolResult(
        content=[{"type": "text", "text": json.dumps(results, ensure_ascii=False)}],
        meta={"count": len(results)},
    )


def spec_memory_delete() -> ToolSpec:
    return ToolSpec(
        name="memory.delete",
        description="Delete a stored value by key.",
        input_schema={
            "type": "object",
            "properties": {
                "namespace": {"type": "string", "default": "default"},
                "key": {"type": "string"},
            },
            "required": ["key"],
            "additionalProperties": False,
        },
        risk="medium",
        annotations={"builtin": True},
    )


def handle_memory_delete(call: ToolCall, *, store: MemoryStore) -> ToolResult:
    namespace = str(call.args.get("namespace", "default"))
    key = call.args.get("key")
    if not isinstance(key, str) or not key:
        return ToolResult(
            content=[{"type": "text", "text": "缺少 key 參數。"}],
            is_error=True,
            meta={"status": "invalid_args"},
        )
    try:
        store.delete(namespace, key)
    except FileNotFoundError:
        return ToolResult(
            content=[{"type": "text", "text": "找不到記錄。"}],
            is_error=True,
            meta={"status": "not_found"},
        )
    except OSError as exc:
        return ToolResult(
            content=[{"type": "text", "text": f"刪除記憶失敗：{exc}"}],
            is_error=True,
            meta={"status": "io_error"},
        )
    return ToolResult(content=[{"type": "text", "text": "已刪除記錄。"}])


def register_memory_tools(registry: Any, *, store: MemoryStore) -> None:
    registry.register(spec_memory_put(), lambda call: handle_memory_put(call, store=store))
    registry.register(spec_memory_get(), lambda call: handle_memory_get(call, store=store))
    registry.register(spec_memory_search(), lambda call: handle_memory_search(call, store=store))
    registry.register(spec_memory_delete(), lambda call: handle_memory_delete(call, store=store))
