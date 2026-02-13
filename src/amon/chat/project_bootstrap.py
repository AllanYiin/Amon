"""Project bootstrap helpers for chat interfaces."""

from __future__ import annotations

import re
from typing import Any, Callable

from amon.core import AmonCore, ProjectRecord

PlanBuilder = Callable[[str, str], tuple[str, dict]]


TASK_INTENT_KEYWORDS = (
    "請",
    "幫我",
    "協助",
    "處理",
    "完成",
    "製作",
    "整理",
    "規劃",
    "建立",
    "產生",
    "撰寫",
    "設計",
    "分析",
    "修正",
)


def should_bootstrap_project(
    project_id: str | None,
    router_type: str,
    message: str = "",
    *,
    is_slash_command: bool = False,
) -> bool:
    if project_id:
        return False
    if router_type in {"command_plan", "graph_patch_plan"}:
        return True
    if is_task_intent_message(message):
        return True
    return is_slash_command


def build_project_name(message: str, plan_type: str, build_plan_from_message: PlanBuilder) -> str:
    command_name = ""
    args: dict[str, Any] = {}
    try:
        command_name, args = build_plan_from_message(message, plan_type)
    except ValueError:
        command_name = ""
        args = {}
    name = ""
    if isinstance(args, dict) and args:
        suffix_parts = _select_args_for_name(args)
        if suffix_parts:
            name = f"{command_name} {' '.join(suffix_parts)}"
        else:
            name = command_name
    else:
        snippet = summarize_task_message(message)
        if snippet:
            name = snippet
    if not name:
        name = command_name or "未命名任務"
    normalized = " ".join(name.split())
    return _normalize_project_name(normalized)


def summarize_task_message(message: str) -> str:
    normalized = " ".join(message.strip().split())
    if not normalized:
        return ""

    stripped = normalized
    for prefix in ("請幫我", "請協助", "協助", "幫我", "請", "麻煩", "可以幫我"):
        if stripped.startswith(prefix):
            stripped = stripped[len(prefix) :].strip()
            break

    compact = re.sub(r"\s+", "", stripped)
    compare_match = re.search(r"比較([A-Za-z0-9_-]+)與([A-Za-z0-9_-]+)", compact, flags=re.IGNORECASE)
    if compare_match:
        left = compare_match.group(1)
        right = compare_match.group(2)
        action = "撰寫" if ("撰寫" in compact or "文章" in compact) else "比較"
        suffix = "技術文章" if ("技術文章" in compact or "文章" in compact) else "比較"
        return f"{action}{left}與{right}{suffix}"

    return stripped


def bootstrap_project_if_needed(
    *,
    core: AmonCore,
    project_id: str | None,
    message: str,
    router_type: str,
    build_plan_from_message: PlanBuilder,
    is_slash_command: bool = False,
) -> ProjectRecord | None:
    if not should_bootstrap_project(project_id, router_type, message, is_slash_command=is_slash_command):
        return None
    plan_type = router_type if router_type in {"command_plan", "graph_patch_plan"} else "command_plan"
    name = build_project_name(message, plan_type, build_plan_from_message)
    return core.create_project(name)


def is_task_intent_message(message: str) -> bool:
    normalized = " ".join(message.split())
    if not normalized:
        return False
    lowered = normalized.lower()
    if lowered in {"hi", "hello", "哈囉", "你好", "早安", "晚安"}:
        return False
    return any(keyword in normalized for keyword in TASK_INTENT_KEYWORDS)


def resolve_project_id_from_message(core: AmonCore, message: str) -> str | None:
    message_text = " ".join(message.split())
    if not message_text:
        return None
    message_lower = message_text.lower()
    message_compact = "".join(message_lower.split())
    candidates: list[tuple[int, str]] = []
    for record in core.list_projects():
        project_id = record.project_id.strip()
        project_name = " ".join(record.name.split())
        if not project_id:
            continue
        project_id_lower = project_id.lower()
        project_name_lower = project_name.lower()
        project_name_compact = "".join(project_name_lower.split())
        if project_id_lower in message_lower:
            candidates.append((300 + len(project_id_lower), project_id))
        if project_name and project_name_lower in message_lower:
            candidates.append((200 + len(project_name_lower), project_id))
        elif project_name_compact and project_name_compact in message_compact:
            candidates.append((100 + len(project_name_compact), project_id))
    if not candidates:
        return None
    candidates.sort(reverse=True)
    return candidates[0][1]


def _select_args_for_name(args: dict[str, Any]) -> list[str]:
    parts: list[str] = []
    preferred_keys = ["name", "title", "project_id", "id"]
    for key in preferred_keys:
        if key in args and args[key]:
            parts.append(_format_arg(key, args[key]))
            if len(parts) == 2:
                return parts
    for key, value in args.items():
        if value:
            parts.append(_format_arg(key, value))
            if len(parts) == 2:
                break
    return parts


def _format_arg(key: str, value: Any) -> str:
    value_text = " ".join(str(value).split())
    if not value_text:
        return key
    return f"{key}={value_text}"


def _normalize_project_name(name: str) -> str:
    cleaned = " ".join(name.split()).strip()
    if not cleaned:
        return "未命名任務"
    has_cjk = any(_is_cjk(char) for char in cleaned)
    if has_cjk:
        compact = re.sub(r"\s+", "", cleaned)
        result_chars: list[str] = []
        cjk_count = 0
        for char in compact:
            if _is_cjk(char):
                if cjk_count >= 10:
                    break
                cjk_count += 1
                result_chars.append(char)
                continue
            if char.isalnum() and cjk_count < 10:
                result_chars.append(char)
        result = "".join(result_chars).strip("-_ ")
        while result.endswith(("的", "了", "與", "和")):
            result = result[:-1]
        return result or "新任務"

    words = cleaned.split()
    result = " ".join(words[:5]).strip()
    return result or "new task"


def _is_cjk(char: str) -> bool:
    code = ord(char)
    return (
        0x4E00 <= code <= 0x9FFF
        or 0x3400 <= code <= 0x4DBF
        or 0xF900 <= code <= 0xFAFF
    )
