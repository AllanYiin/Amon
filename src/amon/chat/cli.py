"""Chat REPL CLI for Amon."""

from __future__ import annotations

import json
from typing import Callable

from amon.chat.project_bootstrap import bootstrap_project_if_needed
from amon.chat.router import RouterResult, route_intent
from amon.chat.session_store import append_event, create_chat_session
from amon.commands.executor import CommandPlan, execute
from amon.core import AmonCore
from amon.fs.safety import make_change_plan


def run_chat_repl(
    core: AmonCore,
    project_id: str | None,
    input_func: Callable[[str], str] = input,
    output_func: Callable[[str], None] = print,
) -> str:
    core.ensure_base_structure()
    chat_id: str | None = None
    project_path = None
    if project_id:
        project_path = core.get_project_path(project_id)
        chat_id = create_chat_session(project_id)
        output_func(f"已建立 chat session：{chat_id}")
    else:
        output_func("未指定專案，將在第一個任務指令時自動建立專案。")

    last_run_id: str | None = None
    while True:
        try:
            message = input_func("你：").strip()
        except (EOFError, KeyboardInterrupt):
            output_func("已結束對話。")
            break

        if not message:
            continue

        if message.lower() in {"exit", "quit", "/exit", "/quit"}:
            if chat_id and project_id:
                append_event(chat_id, {"type": "system", "text": "對話已結束", "project_id": project_id})
            output_func("已結束對話。")
            break

        try:
            is_slash_command = message.startswith("/")
            if is_slash_command:
                router_result = RouterResult(type="command_plan")
            else:
                router_result = route_intent(message, project_id=project_id, run_id=last_run_id)
            created_project = bootstrap_project_if_needed(
                core=core,
                project_id=project_id,
                message=message,
                router_type=router_result.type,
                build_plan_from_message=_build_plan_from_message,
                is_slash_command=is_slash_command,
            )
            if created_project:
                project_id = created_project.project_id
                project_path = core.get_project_path(project_id)
                chat_id = create_chat_session(project_id)
                output_func(f"已建立專案：{created_project.name} ({project_id})")
                output_func(f"已建立 chat session：{chat_id}")
                router_result = route_intent(message, project_id=project_id, run_id=last_run_id)
            if chat_id and project_id:
                append_event(chat_id, {"type": "user", "text": message, "project_id": project_id})
            if chat_id and project_id:
                append_event(
                    chat_id,
                    {
                        "type": "router",
                        "text": router_result.type,
                        "project_id": project_id,
                    },
                )
            if router_result.type in {"command_plan", "graph_patch_plan"}:
                if not (project_id and chat_id):
                    output_func("請先建立或指定專案。")
                    continue
                _handle_plan_message(
                    core,
                    project_id,
                    chat_id,
                    message,
                    router_result.type,
                    input_func,
                    output_func,
                )
                continue
            if router_result.type == "chat_response":
                if not project_path or not (project_id and chat_id):
                    output_func("請先建立或指定專案。")
                    continue
                output_func("Amon：")
                response = core.run_single(message, project_path=project_path)
                append_event(chat_id, {"type": "assistant", "text": response, "project_id": project_id})
                continue
            output_func("目前尚未支援此類型的操作。")
            if chat_id and project_id:
                append_event(
                    chat_id,
                    {"type": "system", "text": "尚未支援此類型", "project_id": project_id},
                )
        except Exception as exc:  # noqa: BLE001
            core.logger.error("Chat 處理失敗：%s", exc, exc_info=True)
            output_func("處理失敗，請查看 logs/amon.log。")
            if chat_id and project_id:
                append_event(chat_id, {"type": "error", "text": str(exc), "project_id": project_id})

    return chat_id or ""


def _handle_plan_message(
    core: AmonCore,
    project_id: str,
    chat_id: str,
    message: str,
    plan_type: str,
    input_func: Callable[[str], str],
    output_func: Callable[[str], None],
) -> None:
    command_name, args = _build_plan_from_message(message, plan_type)
    plan = CommandPlan(
        name=command_name,
        args=args,
        project_id=project_id,
        chat_id=chat_id,
        metadata={"plan_type": plan_type},
    )
    append_event(
        chat_id,
        {
            "type": "plan_created",
            "text": command_name,
            "project_id": project_id,
        },
    )
    result = execute(plan, confirmed=False)
    append_event(
        chat_id,
        {
            "type": "command_result",
            "text": json.dumps(result, ensure_ascii=False),
            "project_id": project_id,
            "command": command_name,
        },
    )
    if result.get("status") == "confirm_required":
        plan_card = result.get("plan_card") or make_change_plan([])
        append_event(
            chat_id,
            {
                "type": "plan_card",
                "text": plan_card,
                "project_id": project_id,
                "command": command_name,
            },
        )
        output_func(plan_card)
        confirmed = _prompt_confirm(input_func, output_func)
        append_event(
            chat_id,
            {
                "type": "plan_confirm",
                "text": "confirmed" if confirmed else "cancelled",
                "project_id": project_id,
                "command": command_name,
            },
        )
        if not confirmed:
            output_func("已取消。")
            return
        result = execute(plan, confirmed=True)
        append_event(
            chat_id,
            {
                "type": "command_result",
                "text": json.dumps(result, ensure_ascii=False),
                "project_id": project_id,
                "command": command_name,
            },
        )
    output_func(json.dumps(result, ensure_ascii=False, indent=2))


def _build_plan_from_message(message: str, plan_type: str) -> tuple[str, dict]:
    if plan_type == "graph_patch_plan":
        return "graph.patch", {"message": message}

    if message.startswith("/"):
        return _parse_slash_command(message)
    return _parse_natural_command(message)


def _parse_slash_command(message: str) -> tuple[str, dict]:
    tokens = message[1:].strip().split()
    if not tokens:
        raise ValueError("command 不可為空")
    command_name = tokens[0]
    rest_tokens = tokens[1:]
    if "." not in command_name and rest_tokens:
        command_name = f"{command_name}.{rest_tokens[0]}"
        rest_tokens = rest_tokens[1:]
    args = _parse_args(rest_tokens)
    return command_name, args


def _parse_natural_command(message: str) -> tuple[str, dict]:
    if "列出專案" in message:
        return "projects.list", {}
    if "建立專案" in message:
        name = _extract_tail(message, "建立專案")
        if not name:
            raise ValueError("請提供專案名稱")
        return "projects.create", {"name": name}
    if "刪除專案" in message:
        project_id = _extract_tail(message, "刪除專案")
        if not project_id:
            raise ValueError("請提供專案 ID")
        return "projects.delete", {"project_id": project_id}
    if "還原專案" in message:
        trash_id = _extract_tail(message, "還原專案")
        if not trash_id:
            raise ValueError("請提供 trash ID")
        return "projects.restore", {"trash_id": trash_id}
    raise ValueError("無法解析指令")


def _parse_args(tokens: list[str]) -> dict:
    if not tokens:
        return {}
    payload = " ".join(tokens).strip()
    if not payload:
        return {}
    try:
        data = json.loads(payload)
    except json.JSONDecodeError as exc:
        raise ValueError("args 需為 JSON 格式") from exc
    if not isinstance(data, dict):
        raise ValueError("args 需為 JSON 物件")
    return data


def _extract_tail(message: str, keyword: str) -> str:
    _, _, tail = message.partition(keyword)
    return tail.strip()


def _prompt_confirm(input_func: Callable[[str], str], output_func: Callable[[str], None]) -> bool:
    response = input_func("請確認是否繼續？(y/N)：").strip().lower()
    if response == "y":
        output_func("已確認執行。")
        return True
    output_func("未確認，將取消。")
    return False
