"""LLM-based router for chat messages."""

from __future__ import annotations

import json
import logging
from dataclasses import asdict
from typing import Any, Iterable, Protocol

from amon.config import ConfigLoader
from amon.models import ProviderError, build_provider

from .router_types import RouterResult

logger = logging.getLogger(__name__)

TEAM_MODE_STRONG_SIGNALS = (
    "研究報告",
    "白皮書",
    "論文",
    "研究計畫",
    "實驗設計",
    "多代理",
    "多 agent",
    "multi-agent",
    "team",
)


class LLMClient(Protocol):
    def generate_stream(self, messages: list[dict[str, str]], model: str | None = None) -> Iterable[str]:
        ...


def route_with_llm(
    message: str,
    context: dict[str, Any],
    commands_registry: list[dict[str, Any]],
    project_id: str | None = None,
    llm_client: LLMClient | None = None,
    model: str | None = None,
) -> RouterResult:
    if message is None:
        message = ""

    try:
        if llm_client is None:
            llm_client, model = _build_default_client(project_id, model)
        payload = {
            "message": message,
            "context": context,
            "commands_registry": commands_registry,
            "router_result_schema": _router_schema(),
        }
        messages = [
            {
                "role": "system",
                "content": _system_prompt(),
            },
            {
                "role": "user",
                "content": json.dumps(payload, ensure_ascii=False),
            },
        ]
        output_text = _collect_stream(llm_client, messages, model)
        return _parse_router_result(output_text)
    except (ProviderError, OSError, ValueError) as exc:
        logger.warning("LLM router 失敗，改用安全模式：%s", exc)
    except Exception as exc:  # noqa: BLE001
        logger.error("LLM router 未預期錯誤：%s", exc, exc_info=True)
    return RouterResult(type="chat_response", confidence=0.0, reason="路由失敗，已切換安全模式")


def choose_execution_mode_with_llm(
    message: str,
    *,
    project_id: str | None = None,
    llm_client: LLMClient | None = None,
    model: str | None = None,
) -> str:
    if message is None:
        message = ""
    normalized = " ".join(message.split())
    if not normalized:
        return "single"
    try:
        if llm_client is None:
            llm_client, model = _build_default_client(project_id, model)
        messages = [
            {"role": "system", "content": _execution_mode_system_prompt()},
            {
                "role": "user",
                "content": json.dumps({"message": normalized, "allowed_modes": ["single", "self_critique", "team"]}, ensure_ascii=False),
            },
        ]
        output_text = _collect_stream(llm_client, messages, model)
        mode = _parse_execution_mode(output_text)
        if mode in {"single", "self_critique", "team"}:
            if mode == "team" and not _allow_team_mode(normalized):
                return "single"
            return mode
    except (ProviderError, OSError, ValueError) as exc:
        logger.warning("LLM execution mode 判斷失敗，改用預設 single：%s", exc)
    except Exception as exc:  # noqa: BLE001
        logger.error("LLM execution mode 未預期錯誤：%s", exc, exc_info=True)
    return "single"


def should_continue_run_with_llm(
    *,
    user_message: str,
    last_assistant_text: str | None,
    project_id: str | None = None,
    llm_client: LLMClient | None = None,
    model: str | None = None,
) -> bool:
    normalized_user = " ".join((user_message or "").split())
    normalized_assistant = " ".join((last_assistant_text or "").split())
    if not normalized_user or not normalized_assistant:
        return False
    try:
        if llm_client is None:
            llm_client, model = _build_default_client(project_id, model)
        payload = {
            "assistant_previous_message": normalized_assistant,
            "user_current_message": normalized_user,
            "output_schema": {
                "continue_run": "boolean",
                "confidence": "number",
            },
        }
        messages = [
            {"role": "system", "content": _run_continuation_system_prompt()},
            {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
        ]
        output_text = _collect_stream(llm_client, messages, model)
        return _parse_run_continuation(output_text)
    except (ProviderError, OSError, ValueError) as exc:
        logger.warning("LLM run 延續判斷失敗，改用預設 false：%s", exc)
    except Exception as exc:  # noqa: BLE001
        logger.error("LLM run 延續判斷未預期錯誤：%s", exc, exc_info=True)
    return False


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


def _parse_router_result(raw_text: str) -> RouterResult:
    if not raw_text:
        return RouterResult(type="chat_response", confidence=0.0, reason="空白回應，已切換安全模式")
    cleaned = _strip_code_fences(raw_text)
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError:
        return RouterResult(type="chat_response", confidence=0.0, reason="JSON 格式錯誤，已切換安全模式")
    if not isinstance(data, dict):
        return RouterResult(type="chat_response", confidence=0.0, reason="路由格式錯誤，已切換安全模式")
    return _coerce_router_result(data)


def _coerce_router_result(data: dict[str, Any]) -> RouterResult:
    result = RouterResult(
        type=str(data.get("type") or "chat_response"),
        confidence=float(data.get("confidence") or 0.0),
        api=data.get("api") if isinstance(data.get("api"), str) else None,
        args=data.get("args") if isinstance(data.get("args"), dict) else {},
        requires_confirm=bool(data.get("requires_confirm") or False),
        reason=data.get("reason") if isinstance(data.get("reason"), str) else None,
    )
    return result


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


def _system_prompt() -> str:
    schema = json.dumps(_router_schema(), ensure_ascii=False, indent=2)
    return (
        "你是路由器，需要判斷使用者訊息的意圖。"
        "請只輸出符合 JSON schema 的單一 JSON 物件，不要輸出 Markdown 或任何說明。"
        "如果不確定，請以 chat_response 回覆。"
        f"JSON schema 如下：{schema}"
    )


def _execution_mode_system_prompt() -> str:
    return (
        "你是執行模式路由器。"
        "請根據使用者訊息判斷最適合的 execution mode。"
        "只允許輸出 JSON，格式為 {\"mode\":\"single|self_critique|team\"}。"
        "不得輸出額外文字。"
    )


def _run_continuation_system_prompt() -> str:
    return (
        "你是對話 run 延續判斷器。"
        "請判斷使用者目前訊息是否是在回覆 assistant 上一則訊息，且語意上應該延續同一個任務 run。"
        "若是同一任務的追問回覆或補充，continue_run=true；若是改題、新任務或無關訊息，continue_run=false。"
        "只允許輸出 JSON，格式為 {\"continue_run\": true|false, \"confidence\": 0~1}。"
        "不得輸出額外文字。"
    )


def _parse_run_continuation(raw_text: str) -> bool:
    cleaned = _strip_code_fences(raw_text)
    if not cleaned:
        raise ValueError("空白回應")
    payload = json.loads(cleaned)
    if not isinstance(payload, dict):
        raise ValueError("run continuation 回傳格式錯誤")
    if "continue_run" not in payload:
        raise ValueError("run continuation 缺少 continue_run")
    return bool(payload.get("continue_run"))


def _parse_execution_mode(raw_text: str) -> str:
    cleaned = _strip_code_fences(raw_text)
    if not cleaned:
        return ""
    payload = json.loads(cleaned)
    if not isinstance(payload, dict):
        return ""
    mode = str(payload.get("mode") or "").strip().lower()
    return mode


def _allow_team_mode(message: str) -> bool:
    lowered = message.lower()
    compact = "".join(lowered.split())
    return any(signal in lowered or signal.replace(" ", "") in compact for signal in TEAM_MODE_STRONG_SIGNALS)


def _router_schema() -> dict[str, Any]:
    return asdict(
        RouterResult(
            type="command_plan",
            confidence=0.75,
            api="projects.list",
            args={},
            requires_confirm=False,
            reason="示例",
        )
    )
