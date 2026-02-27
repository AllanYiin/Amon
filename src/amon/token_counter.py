from __future__ import annotations

import importlib
import importlib.util
import json
from dataclasses import dataclass
from typing import Any


@dataclass
class TokenCountResult:
    tokens: int | None
    method: str
    available: bool


def _estimate_tokens_from_text(text: str) -> int:
    # Deterministic fallback: approximately 1 token per 4 chars, with a minimum cost for non-empty payload.
    normalized = text.strip()
    if not normalized:
        return 0
    return max(1, (len(normalized) + 3) // 4)


def _get_provider_type(effective_config: dict[str, Any], provider_name: str) -> str:
    if not provider_name:
        return ""
    provider_cfg = (effective_config.get("providers") or {}).get(provider_name) or {}
    return str(provider_cfg.get("type") or "").strip().lower()


def _get_provider_model(effective_config: dict[str, Any], provider_name: str) -> str:
    if not provider_name:
        return ""
    provider_cfg = (effective_config.get("providers") or {}).get(provider_name) or {}
    return str(provider_cfg.get("model") or "").strip()


def _serialize_payload(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    try:
        return json.dumps(value, ensure_ascii=False)
    except (TypeError, ValueError):
        return str(value)


def _openai_tiktoken_count(text: str, model: str) -> TokenCountResult:
    if not text.strip():
        return TokenCountResult(tokens=0, method="openai_tiktoken", available=True)
    if importlib.util.find_spec("tiktoken") is None:
        return TokenCountResult(tokens=None, method="openai_tiktoken_unavailable", available=False)
    module = importlib.import_module("tiktoken")
    try:
        try:
            encoding = module.encoding_for_model(model or "gpt-4o-mini")
        except KeyError:
            encoding = module.get_encoding("cl100k_base")
        return TokenCountResult(tokens=len(encoding.encode(text)), method="openai_tiktoken", available=True)
    except Exception:
        return TokenCountResult(tokens=None, method="openai_tiktoken_unavailable", available=False)


def count_non_dialogue_tokens(value: Any, *, effective_config: dict[str, Any]) -> TokenCountResult:
    text = _serialize_payload(value)
    if not text.strip():
        return TokenCountResult(tokens=0, method="empty", available=True)

    provider_name = str((effective_config.get("amon") or {}).get("provider") or "").strip()
    provider_type = _get_provider_type(effective_config, provider_name)
    provider_model = _get_provider_model(effective_config, provider_name)

    if provider_type in {"openai", "openai_compatible", "openai-compatible"}:
        result = _openai_tiktoken_count(text, provider_model)
        if result.available and result.tokens is not None:
            return result
        return TokenCountResult(tokens=_estimate_tokens_from_text(text), method="estimated_chars_div4", available=False)
    return TokenCountResult(tokens=_estimate_tokens_from_text(text), method=f"{provider_type or 'unknown'}_estimated_chars_div4", available=False)


def extract_dialogue_input_tokens(recent_events: list[dict[str, Any]]) -> TokenCountResult:
    total = 0
    seen = False

    for event in recent_events:
        usage = event.get("usage") if isinstance(event, dict) else None
        if not isinstance(usage, dict):
            usage = {}
        candidates = [
            usage.get("prompt_tokens"),
            usage.get("input_tokens"),
            event.get("prompt_tokens") if isinstance(event, dict) else None,
            event.get("input_tokens") if isinstance(event, dict) else None,
        ]
        for raw in candidates:
            try:
                value = int(raw)
            except (TypeError, ValueError):
                continue
            if value < 0:
                continue
            total += value
            seen = True
            break

    if not seen:
        return TokenCountResult(tokens=None, method="api_usage_unavailable", available=False)
    return TokenCountResult(tokens=total, method="api_usage", available=True)
