"""Graph patch utilities."""

from __future__ import annotations

from copy import deepcopy
from typing import Any


Patch = dict[str, Any]


def validate_patches(patches: list[Patch]) -> None:
    if not isinstance(patches, list):
        raise ValueError("patches 需為陣列")
    for index, patch in enumerate(patches):
        if not isinstance(patch, dict):
            raise ValueError(f"patch #{index} 需為物件")
        op = patch.get("op")
        path = patch.get("path")
        if op not in {"set", "remove"}:
            raise ValueError(f"patch #{index} op 僅支援 set/remove")
        if not isinstance(path, str) or not path.strip():
            raise ValueError(f"patch #{index} path 不可為空")
        if op == "set" and "value" not in patch:
            raise ValueError(f"patch #{index} set 需要 value")


def apply_patch(graph_json: dict[str, Any], patches: list[Patch]) -> dict[str, Any]:
    validate_patches(patches)
    updated = deepcopy(graph_json)
    for patch in patches:
        op = patch["op"]
        tokens = _parse_json_path(str(patch["path"]))
        parent, last_token = _locate_json_target(updated, tokens)
        if op == "set":
            _set_value(parent, last_token, patch.get("value"))
        elif op == "remove":
            _remove_value(parent, last_token)
    return updated


def _set_value(parent: Any, token: Any, value: Any) -> None:
    if isinstance(token, int):
        if not isinstance(parent, list):
            raise ValueError("JSONPath 指向的陣列不存在")
        if token < 0:
            raise ValueError("JSONPath 索引不可為負數")
        if token < len(parent):
            parent[token] = value
            return
        if token == len(parent):
            parent.append(value)
            return
        raise ValueError("JSONPath 指向的陣列不存在")
    if not isinstance(parent, dict):
        raise ValueError("JSONPath 指向的欄位不存在")
    parent[token] = value


def _remove_value(parent: Any, token: Any) -> None:
    if isinstance(token, int):
        if not isinstance(parent, list) or token >= len(parent):
            raise ValueError("JSONPath 指向的陣列不存在")
        parent.pop(token)
        return
    if not isinstance(parent, dict) or token not in parent:
        raise ValueError("JSONPath 指向的欄位不存在")
    parent.pop(token)


def _parse_json_path(json_path: str) -> list[Any]:
    if not json_path:
        raise ValueError("JSONPath 不可為空")
    path = json_path.strip()
    if path.startswith("$"):
        path = path[1:]
    if path.startswith("."):
        path = path[1:]
    tokens: list[Any] = []
    index = 0
    while index < len(path):
        if path[index] == ".":
            index += 1
            continue
        if path[index] == "[":
            end = path.find("]", index)
            if end == -1:
                raise ValueError("JSONPath 缺少 ]")
            raw = path[index + 1 : end].strip()
            if (raw.startswith("\"") and raw.endswith("\"")) or (raw.startswith("'") and raw.endswith("'")):
                raw = raw[1:-1]
                tokens.append(raw)
            elif raw.isdigit():
                tokens.append(int(raw))
            elif raw:
                tokens.append(raw)
            else:
                raise ValueError("JSONPath 索引不可為空")
            index = end + 1
            continue
        next_index = index
        while next_index < len(path) and path[next_index] not in ".[":
            next_index += 1
        token = path[index:next_index]
        if not token:
            raise ValueError("JSONPath 片段不可為空")
        tokens.append(token)
        index = next_index
    if not tokens:
        raise ValueError("JSONPath 不可為空")
    return tokens


def _locate_json_target(payload: Any, tokens: list[Any]) -> tuple[Any, Any]:
    current = payload
    for token in tokens[:-1]:
        if isinstance(token, int):
            if not isinstance(current, list) or token >= len(current):
                raise ValueError("JSONPath 指向的陣列不存在")
            current = current[token]
        else:
            if not isinstance(current, dict) or token not in current:
                raise ValueError("JSONPath 指向的欄位不存在")
            current = current[token]
    return current, tokens[-1]
