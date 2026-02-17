"""Project bootstrap helpers for chat interfaces."""

from __future__ import annotations

import json
import logging
import re
from typing import Any, Callable, Iterable, Protocol

from amon.config import ConfigLoader
from amon.core import AmonCore, ProjectRecord
from amon.models import ProviderError, build_provider

PlanBuilder = Callable[[str, str], tuple[str, dict]]


class LLMClient(Protocol):
    def generate_stream(self, messages: list[dict[str, str]], model: str | None = None) -> Iterable[str]:
        ...


logger = logging.getLogger(__name__)


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

PROFESSIONAL_WRITING_KEYWORDS = (
    "技術文章",
    "專業文件",
    "白皮書",
    "研究",
    "報告",
    "分析文",
    "比較",
)

TEAM_WRITING_KEYWORDS = (
    "研究報告",
    "白皮書",
    "論文",
    "研究計畫",
    "實驗設計",
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
    name = build_project_name(message, plan_type, build_plan_from_message, project_id=project_id)
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


def is_task_intent_message(message: str) -> bool:
    normalized = " ".join(message.split())
    if not normalized:
        return False
    lowered = normalized.lower()
    if lowered in {"hi", "hello", "哈囉", "你好", "早安", "晚安"}:
        return False
    return any(keyword in normalized for keyword in TASK_INTENT_KEYWORDS)


def choose_execution_mode(message: str) -> str:
    """Return suggested execution mode for chat tasks.

    Professional writing tasks should be at least self_critique; research-scale
    writing that implies multi-agent collaboration should run in team mode.
    """

    normalized = " ".join(message.split())
    if not normalized:
        return "single"
    compact_lower = "".join(normalized.lower().split())
    if any(keyword in compact_lower for keyword in TEAM_WRITING_KEYWORDS):
        return "team"
    if any(keyword in normalized for keyword in PROFESSIONAL_WRITING_KEYWORDS):
        return "self_critique"
    return "single"


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
        result = _compress_cjk_name(cleaned)
        while result.endswith(("的", "了", "與", "和")):
            result = result[:-1]
        return result or "新任務"

    result = _compress_english_name(cleaned)
    return result or "new task"


def _compress_cjk_name(text: str) -> str:
    compact = re.sub(r"\s+", "", text)
    compact = re.sub(r"^(請幫我|請協助|幫我|協助|請|麻煩|可以幫我)", "", compact)
    compact = re.sub(r"(嗎|呢|吧)$", "", compact)
    action_match = re.match(r"(開發|建立|製作|撰寫|整理|規劃|設計|分析|修正|產生|完成)(.+)", compact)
    if action_match:
        action, subject = action_match.groups()
        subject = re.sub(r"^(一個|一份|一套|一篇)", "", subject)
        subject = re.sub(r"(並|而且|以及|且).*$", "", subject)
        candidate = f"{action}{subject}"
        if _cjk_length(candidate) <= 10:
            return candidate.strip("-_ ")

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
    return "".join(result_chars).strip("-_ ")


def _compress_english_name(text: str) -> str:
    words = text.split()
    if len(words) <= 5:
        return " ".join(words).strip()

    stop_words = {"please", "kindly", "the", "a", "an", "to", "for", "of", "and", "with", "on", "in"}
    meaningful: list[str] = []
    for word in words:
        plain = re.sub(r"[^A-Za-z0-9_-]", "", word)
        if not plain:
            continue
        if plain.lower() in stop_words and meaningful:
            continue
        meaningful.append(plain)
        if len(meaningful) == 5:
            break
    if meaningful:
        return " ".join(meaningful).strip()
    return " ".join(words[:5]).strip()


def _cjk_length(text: str) -> int:
    return sum(1 for char in text if _is_cjk(char))


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


def _is_cjk(char: str) -> bool:
    code = ord(char)
    return (
        0x4E00 <= code <= 0x9FFF
        or 0x3400 <= code <= 0x4DBF
        or 0xF900 <= code <= 0xFAFF
    )
