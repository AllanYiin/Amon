"""Project bootstrap helpers for chat interfaces."""

from __future__ import annotations

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
        snippet = " ".join(message.strip().split())
        if snippet:
            name = snippet[:30]
    if not name:
        name = command_name or "未命名任務"
    return " ".join(name.split())


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
