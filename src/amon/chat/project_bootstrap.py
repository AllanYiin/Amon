"""Project bootstrap helpers for chat interfaces."""

from __future__ import annotations

from typing import Any, Callable

from amon.core import AmonCore, ProjectRecord

PlanBuilder = Callable[[str, str], tuple[str, dict]]


def should_bootstrap_project(
    project_id: str | None,
    router_type: str,
    *,
    is_slash_command: bool = False,
) -> bool:
    if project_id:
        return False
    if router_type in {"command_plan", "graph_patch_plan"}:
        return True
    return is_slash_command


def build_project_name(message: str, plan_type: str, build_plan_from_message: PlanBuilder) -> str:
    command_name, args = build_plan_from_message(message, plan_type)
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
    if not should_bootstrap_project(project_id, router_type, is_slash_command=is_slash_command):
        return None
    plan_type = router_type if router_type in {"command_plan", "graph_patch_plan"} else "command_plan"
    name = build_project_name(message, plan_type, build_plan_from_message)
    return core.create_project(name)


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
