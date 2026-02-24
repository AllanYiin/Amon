"""Project bootstrap helpers for chat interfaces."""

from __future__ import annotations

import json
import logging
from typing import Any, Callable, Iterable, Protocol

from amon.chat.execution_mode import decide_execution_mode
from amon.config import ConfigLoader
from amon.core import AmonCore, ProjectRecord
from amon.models import ProviderError, build_provider

PlanBuilder = Callable[[str, str], tuple[str, dict]]


class LLMClient(Protocol):
    def generate_stream(self, messages: list[dict[str, str]], model: str | None = None) -> Iterable[str]:
        ...


logger = logging.getLogger(__name__)


def should_bootstrap_project(
    project_id: str | None,
    router_type: str,
    message: str = "",
    *,
    is_slash_command: bool = False,
    llm_client: LLMClient | None = None,
    model: str | None = None,
) -> bool:
    if project_id:
        return False
    if router_type in {"command_plan", "graph_patch_plan"}:
        return True
    if is_task_intent_message(message, project_id=project_id, llm_client=llm_client, model=model):
        return True
    return is_slash_command


def build_project_name(
    message: str,
    plan_type: str,
    build_plan_from_message: PlanBuilder,
    *,
    project_id: str | None = None,
    llm_client: LLMClient | None = None,
    model: str | None = None,
) -> str:
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
    llm_summary = _summarize_project_name_with_llm(
        normalized,
        project_id=project_id,
        llm_client=llm_client,
        model=model,
    )
    return _normalize_project_name(llm_summary or normalized)


def summarize_task_message(message: str) -> str:
    normalized = " ".join(message.strip().split())
    if not normalized:
        return ""
    return normalized


def bootstrap_project_if_needed(
    *,
    core: AmonCore,
    project_id: str | None,
    message: str,
    router_type: str,
    build_plan_from_message: PlanBuilder,
    is_slash_command: bool = False,
    llm_client: LLMClient | None = None,
    model: str | None = None,
) -> ProjectRecord | None:
    if not should_bootstrap_project(
        project_id,
        router_type,
        message,
        is_slash_command=is_slash_command,
        llm_client=llm_client,
        model=model,
    ):
        return None
    plan_type = router_type if router_type in {"command_plan", "graph_patch_plan"} else "command_plan"
    name = build_project_name(
        message,
        plan_type,
        build_plan_from_message,
        project_id=project_id,
        llm_client=llm_client,
        model=model,
    )
    return core.create_project(name)


def _summarize_project_name_with_llm(
    source_text: str,
    *,
    project_id: str | None,
    llm_client: LLMClient | None,
    model: str | None,
) -> str:
    text = " ".join(source_text.split()).strip()
    if not text:
        return ""
    try:
        selected_model = model
        client = llm_client
        if client is None:
            client, selected_model = _build_default_client(project_id=project_id, model=model)
        messages = [
            {"role": "system", "content": _project_name_system_prompt()},
            {
                "role": "user",
                "content": json.dumps({"text": text, "output_schema": {"name": "string"}}, ensure_ascii=False),
            },
        ]
        raw = _collect_stream(client, messages, selected_model)
        return _parse_llm_project_name(raw)
    except (ProviderError, OSError, ValueError, json.JSONDecodeError) as exc:
        logger.warning("LLM 專案名稱摘要失敗，改用本地規則：%s", exc)
    except Exception as exc:  # noqa: BLE001
        logger.error("LLM 專案名稱摘要未預期錯誤：%s", exc, exc_info=True)
    return ""


def is_task_intent_message(
    message: str,
    *,
    project_id: str | None = None,
    llm_client: LLMClient | None = None,
    model: str | None = None,
) -> bool:
    normalized = " ".join(message.split())
    if not normalized:
        return False
    try:
        selected_model = model
        client = llm_client
        if client is None:
            client, selected_model = _build_default_client(project_id=project_id, model=model)
        messages = [
            {"role": "system", "content": _task_intent_system_prompt()},
            {
                "role": "user",
                "content": json.dumps({"message": normalized, "output_schema": {"is_task_intent": "boolean"}}, ensure_ascii=False),
            },
        ]
        raw = _collect_stream(client, messages, selected_model)
        return _parse_task_intent(raw)
    except (ProviderError, OSError, ValueError, json.JSONDecodeError) as exc:
        logger.warning("LLM 任務意圖判斷失敗，改用預設 False：%s", exc)
    except Exception as exc:  # noqa: BLE001
        logger.error("LLM 任務意圖判斷未預期錯誤：%s", exc, exc_info=True)
    return False


def choose_execution_mode(
    message: str,
    *,
    project_id: str | None = None,
    llm_client: LLMClient | None = None,
    model: str | None = None,
) -> str:
    return decide_execution_mode(
        message,
        project_id=project_id,
        llm_client=llm_client,
        model=model,
    )


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
    return cleaned


def _build_default_client(project_id: str | None, model: str | None) -> tuple[LLMClient, str | None]:
    config = ConfigLoader().resolve(project_id=project_id).effective
    provider_name = config.get("amon", {}).get("provider", "openai")
    provider_cfg = config.get("providers", {}).get(provider_name, {})
    selected_model = model or provider_cfg.get("default_model") or provider_cfg.get("model")
    provider = build_provider(provider_cfg, model=selected_model)
    return provider, selected_model


def _collect_stream(llm_client: LLMClient, messages: list[dict[str, str]], model: str | None) -> str:
    chunks: list[str] = []
    for token in llm_client.generate_stream(messages, model=model):
        chunks.append(token)
    return "".join(chunks).strip()


def _parse_llm_project_name(raw_text: str) -> str:
    cleaned = _strip_code_fences(raw_text)
    if not cleaned:
        return ""
    payload = json.loads(cleaned)
    if not isinstance(payload, dict):
        return ""
    return " ".join(str(payload.get("name") or "").split()).strip()


def _strip_code_fences(text: str) -> str:
    stripped = text.strip()
    if stripped.startswith("```"):
        lines = stripped.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        stripped = "\n".join(lines)
    return stripped.strip()


def _project_name_system_prompt() -> str:
    return (
        "你是專案命名助手。"
        "請根據輸入文字抽取最完整且自然的短語意名稱。"
        "若主要為中文，名稱上限 10 個漢字；若主要為英文，名稱上限 5 個單字。"
        "不要使用截斷符號（例如 ...），不要附加編號或 ID。"
        "只能輸出 JSON：{\"name\":\"...\"}，不得輸出其他文字。"
    )


def _task_intent_system_prompt() -> str:
    return (
        "你是任務意圖分類器。"
        "請判斷使用者訊息是否明確要求系統執行任務，而非單純寒暄或閒聊。"
        "只能輸出 JSON：{\"is_task_intent\": true|false}，不得輸出其他文字。"
    )


def _parse_task_intent(raw_text: str) -> bool:
    cleaned = _strip_code_fences(raw_text)
    if not cleaned:
        return False
    payload = json.loads(cleaned)
    if not isinstance(payload, dict):
        return False
    return bool(payload.get("is_task_intent"))


