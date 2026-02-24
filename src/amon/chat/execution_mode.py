"""Centralized LLM semantic execution-mode decision router."""

from __future__ import annotations

import json
import logging
from typing import Any, Iterable, Protocol

from amon.config import ConfigLoader
from amon.events import EXECUTION_MODE_DECISION, emit_event
from amon.models import ProviderError, build_provider

logger = logging.getLogger(__name__)

_ALLOWED_MODES = {"single", "self_critique", "team", "plan_execute"}


class LLMClient(Protocol):
    def generate_stream(self, messages: list[dict[str, str]], model: str | None = None) -> Iterable[str]:
        ...


def decide_execution_mode(
    message: str,
    project_id: str | None = None,
    llm_client: LLMClient | None = None,
    model: str | None = None,
    *,
    context: dict[str, Any] | None = None,
) -> str:
    normalized = " ".join((message or "").split())
    if not normalized:
        return "single"

    try:
        client = llm_client
        selected_model = model
        if client is None:
            client, selected_model = _build_default_client(project_id=project_id, model=model)

        raw = _classify_mode(
            client,
            selected_model,
            message=normalized,
            project_id=project_id,
            context=context,
        )
        try:
            decision = _parse_and_validate_decision(raw)
        except ValueError as exc:
            repaired = _repair_decision(client, selected_model, raw_output=raw, error=str(exc))
            decision = _parse_and_validate_decision(repaired)
            raw = repaired

        final_mode = _apply_calibration(decision)
        _emit_decision_event(
            project_id=project_id,
            mode=final_mode,
            reason="ok",
            raw_output=raw,
            error="",
            confidence=float(decision["confidence"]),
            requires_planning=bool(decision["requires_planning"]),
        )
        return final_mode
    except Exception as exc:  # noqa: BLE001
        logger.warning("execution mode 決策失敗，改用 plan_execute：%s", exc)
        _emit_decision_event(
            project_id=project_id,
            mode="plan_execute",
            reason="router_invalid_json_fallback",
            raw_output=locals().get("raw", ""),
            error=str(exc),
            confidence=0.0,
            requires_planning=True,
        )
        return "plan_execute"


def _classify_mode(
    llm_client: LLMClient,
    model: str | None,
    *,
    message: str,
    project_id: str | None,
    context: dict[str, Any] | None,
) -> str:
    payload = {
        "message": message,
        "project_id": project_id or "",
        "available_tools": list((context or {}).get("available_tools") or []),
        "available_skills": list((context or {}).get("available_skills") or []),
        "router_context": (context or {}).get("router_context") or {},
    }
    messages = [
        {"role": "system", "content": _classification_system_prompt()},
        {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
    ]
    return _collect_stream(llm_client, messages, model)


def _repair_decision(llm_client: LLMClient, model: str | None, *, raw_output: str, error: str) -> str:
    payload = {
        "raw_output": raw_output,
        "error": error,
        "required_schema": {
            "mode": "single|self_critique|team|plan_execute",
            "confidence": "number between 0 and 1",
            "rationale": ["string"],
            "requires_planning": "boolean",
        },
    }
    messages = [
        {"role": "system", "content": _repair_system_prompt()},
        {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
    ]
    return _collect_stream(llm_client, messages, model)


def _apply_calibration(decision: dict[str, Any]) -> str:
    mode = str(decision["mode"])
    confidence = float(decision["confidence"])
    requires_planning = bool(decision["requires_planning"])
    if mode == "single" and (requires_planning or confidence < 0.60):
        return "plan_execute"
    return mode


def _parse_and_validate_decision(raw_text: str) -> dict[str, Any]:
    cleaned = _strip_code_fences(raw_text)
    if not cleaned:
        raise ValueError("empty_output")
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid_json:{exc}") from exc
    if not isinstance(data, dict):
        raise ValueError("payload_not_object")

    mode = data.get("mode")
    if mode not in _ALLOWED_MODES:
        raise ValueError("invalid_mode")

    confidence = data.get("confidence")
    if not isinstance(confidence, (int, float)):
        raise ValueError("invalid_confidence_type")
    confidence_value = float(confidence)
    if confidence_value < 0.0 or confidence_value > 1.0:
        raise ValueError("invalid_confidence_range")

    rationale = data.get("rationale")
    if not isinstance(rationale, list) or any(not isinstance(item, str) for item in rationale):
        raise ValueError("invalid_rationale")

    requires_planning = data.get("requires_planning")
    if not isinstance(requires_planning, bool):
        raise ValueError("invalid_requires_planning")

    return {
        "mode": mode,
        "confidence": confidence_value,
        "rationale": rationale,
        "requires_planning": requires_planning,
    }


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


def _strip_code_fences(text: str) -> str:
    stripped = (text or "").strip()
    if stripped.startswith("```"):
        lines = stripped.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        stripped = "\n".join(lines)
    return stripped.strip()


def _classification_system_prompt() -> str:
    return (
        "你是 execution mode 語意分類器。"
        "僅能輸出嚴格 JSON，不能有 code fence、不能有額外文字。"
        "模式語意邊界："
        "single：可在單一回合完成，不需多步規劃、不需多工具串接、不需多角色分工。"
        "self_critique：單一 agent，但需高品質自我審查（草稿->檢查->修訂），通常是正式輸出。"
        "team：需要多角色/多專長並行，或任務面向多且需分工（研究、比較、跨領域長文）。"
        "plan_execute：需要多步驟執行、工具調用、檔案或程式修改，或先產 TODO/圖再逐步完成。"
        "校正指令：避免過度選 single；只要任務存在規劃與執行鏈需求，優先選 plan_execute。"
        "輸出格式必須是："
        '{"mode":"single|self_critique|team|plan_execute","confidence":0.0,"rationale":["..."],"requires_planning":true}'
    )


def _repair_system_prompt() -> str:
    return (
        "你是 JSON 修復器。"
        "你會拿到前一次模型輸出與錯誤原因。"
        "請只輸出一個合法 JSON 物件，不要 code fence，不要解釋。"
        "必須符合 schema："
        '{"mode":"single|self_critique|team|plan_execute","confidence":0.0-1.0,"rationale":["string"],"requires_planning":true|false}'
    )


def _emit_decision_event(
    *,
    project_id: str | None,
    mode: str,
    reason: str,
    raw_output: str,
    error: str,
    confidence: float,
    requires_planning: bool,
) -> None:
    try:
        emit_event(
            {
                "type": EXECUTION_MODE_DECISION,
                "scope": "chat.router",
                "actor": "system",
                "payload": {
                    "mode": mode,
                    "reason": reason,
                    "raw_output": raw_output,
                    "error": error,
                    "confidence": confidence,
                    "requires_planning": requires_planning,
                },
                "risk": "low",
                "project_id": project_id or "",
                "run_id": "",
                "node_id": "",
                "request_id": "",
                "tool": "",
            },
            dispatch_hooks=False,
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("execution mode event 記錄失敗：%s", exc)
