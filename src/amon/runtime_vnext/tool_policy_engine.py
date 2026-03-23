"""Policy evaluation for deterministic and delegated tool execution."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import PurePath
from typing import Any

from amon.domain import ToolPolicy


_SIDE_EFFECT_ORDER = {
    "read_only": 0,
    "workspace_write": 1,
    "destructive_write": 2,
    "external_network": 3,
    "sandbox_exec": 4,
}

_DEFAULT_CONFIRMATION_CLASSES = {"destructive_write", "sandbox_exec"}


@dataclass(frozen=True)
class ToolPolicyDecision:
    tool_name: str
    invocation_mode: str
    selected_by: str
    decision: str
    approval_state: str
    side_effect_class: str
    reason: str
    preview: dict[str, Any] = field(default_factory=dict)


class ToolPolicyEngine:
    def evaluate(
        self,
        tool_name: str,
        *,
        payload: dict[str, Any] | None,
        tool_policy: ToolPolicy | None,
        invocation_mode: str,
        selected_by: str,
    ) -> ToolPolicyDecision:
        side_effect_class = _infer_side_effect_class(tool_name)
        preview = _build_preview(tool_name, payload)
        if invocation_mode not in {"deterministic", "delegated"}:
            raise ValueError(f"不合法的 invocation_mode：{invocation_mode}")

        if tool_policy is not None:
            if tool_policy.allowed_tools and tool_name not in tool_policy.allowed_tools:
                return self._deny(tool_name, invocation_mode, selected_by, side_effect_class, "tool 不在 allowed_tools", preview)
            if not _paths_allowed(tool_policy.allowed_paths, payload):
                return self._deny(tool_name, invocation_mode, selected_by, side_effect_class, "路徑超出 allowed_paths", preview)
            if invocation_mode == "delegated" and not tool_policy.delegated_allowed:
                return self._deny(tool_name, invocation_mode, selected_by, side_effect_class, "delegated tool 不被允許", preview)
            if side_effect_class == "external_network" and not tool_policy.allow_network:
                return self._deny(tool_name, invocation_mode, selected_by, side_effect_class, "external_network 未被允許", preview)
            if _ceiling_value(tool_policy.side_effect_ceiling) < _ceiling_value(side_effect_class):
                return self._deny(
                    tool_name,
                    invocation_mode,
                    selected_by,
                    side_effect_class,
                    f"side_effect 超過 ceiling：{tool_policy.side_effect_ceiling}",
                    preview,
                )

        if side_effect_class in _confirmation_classes(tool_policy):
            return self._ask(tool_name, invocation_mode, selected_by, side_effect_class, "需要使用者確認", preview)
        if tool_policy is None and invocation_mode == "delegated":
            return self._deny(tool_name, invocation_mode, selected_by, side_effect_class, "delegated tool 需要 tool policy", preview)
        if invocation_mode == "delegated" and side_effect_class != "read_only":
            return self._ask(tool_name, invocation_mode, selected_by, side_effect_class, "delegated 非唯讀工具需要確認", preview)
        if tool_policy is None and side_effect_class == "external_network":
            return self._deny(tool_name, invocation_mode, selected_by, side_effect_class, "未提供 tool policy", preview)
        return ToolPolicyDecision(
            tool_name=tool_name,
            invocation_mode=invocation_mode,
            selected_by=selected_by,
            decision="allow",
            approval_state="approved",
            side_effect_class=side_effect_class,
            reason="policy allow",
            preview=preview,
        )

    @staticmethod
    def _deny(
        tool_name: str,
        invocation_mode: str,
        selected_by: str,
        side_effect_class: str,
        reason: str,
        preview: dict[str, Any],
    ) -> ToolPolicyDecision:
        return ToolPolicyDecision(
            tool_name=tool_name,
            invocation_mode=invocation_mode,
            selected_by=selected_by,
            decision="deny",
            approval_state="denied",
            side_effect_class=side_effect_class,
            reason=reason,
            preview=preview,
        )

    @staticmethod
    def _ask(
        tool_name: str,
        invocation_mode: str,
        selected_by: str,
        side_effect_class: str,
        reason: str,
        preview: dict[str, Any],
    ) -> ToolPolicyDecision:
        return ToolPolicyDecision(
            tool_name=tool_name,
            invocation_mode=invocation_mode,
            selected_by=selected_by,
            decision="ask",
            approval_state="pending",
            side_effect_class=side_effect_class,
            reason=reason,
            preview=preview,
        )


def _confirmation_classes(tool_policy: ToolPolicy | None) -> set[str]:
    if tool_policy is None:
        return set(_DEFAULT_CONFIRMATION_CLASSES)
    raw = tool_policy.approval_rules.get("require_confirmation_for")
    if not isinstance(raw, list):
        return set(_DEFAULT_CONFIRMATION_CLASSES)
    classes = {str(item).strip() for item in raw if str(item).strip()}
    return classes or set(_DEFAULT_CONFIRMATION_CLASSES)


def _ceiling_value(name: str) -> int:
    return _SIDE_EFFECT_ORDER.get(str(name or "read_only"), 0)


def _infer_side_effect_class(tool_name: str) -> str:
    if tool_name in {"filesystem.delete", "memory.delete"}:
        return "destructive_write"
    if tool_name in {"filesystem.write", "filesystem.patch", "artifacts.write_text", "artifacts.write_file"}:
        return "workspace_write"
    if tool_name.startswith("web.") or ":" in tool_name:
        return "external_network"
    if tool_name in {"process.exec", "sandbox.run"} or tool_name.startswith("terminal."):
        return "sandbox_exec"
    return "read_only"


def _build_preview(tool_name: str, payload: dict[str, Any] | None) -> dict[str, Any]:
    body = dict(payload or {})
    preview: dict[str, Any] = {"tool_name": tool_name}
    for key in ("path", "command", "cwd", "root", "url"):
        value = body.get(key)
        if isinstance(value, str) and value.strip():
            preview[key] = value
    return preview


def _paths_allowed(allowed_paths: list[str], payload: dict[str, Any] | None) -> bool:
    normalized_allowlist = [_normalize_path(item) for item in allowed_paths if _normalize_path(item)]
    if not normalized_allowlist:
        return True
    for key in ("path", "root", "cwd", "workdir"):
        candidate = _normalize_path((payload or {}).get(key))
        if not candidate:
            continue
        if not any(candidate == allowed or candidate.startswith(f"{allowed}/") for allowed in normalized_allowlist):
            return False
    return True


def _normalize_path(value: Any) -> str:
    if not isinstance(value, str) or not value.strip():
        return ""
    normalized = str(PurePath(value.strip())).replace("\\", "/")
    return normalized.rstrip("/")
