"""Shared support matrix for executor binding/compiler/runtime alignment."""

from __future__ import annotations

SPEC_EXECUTOR_TYPES = frozenset({"llm", "tool", "sandbox", "human_gate", "subgraph"})
COMPILED_EXECUTOR_TYPES = frozenset({"llm", "tool", "sandbox", "human_gate"})
DEFERRED_EXECUTOR_TYPES = frozenset({"subgraph"})
UNSUPPORTED_EXECUTOR_TYPE_CODE = "AMON_EXECUTOR_TYPE_001"


def normalize_executor_type(executor_type: str | None) -> str:
    return str(executor_type or "").strip().lower()


def is_compilable_executor_type(executor_type: str | None) -> bool:
    return normalize_executor_type(executor_type) in COMPILED_EXECUTOR_TYPES


def is_deferred_executor_type(executor_type: str | None) -> bool:
    return normalize_executor_type(executor_type) in DEFERRED_EXECUTOR_TYPES


def unsupported_executor_type_message(*, executor_ref: str, executor_type: str | None) -> str:
    normalized = normalize_executor_type(executor_type)
    if normalized == "subgraph":
        return f"subgraph executor 尚未支援：executor_ref={executor_ref}, type={normalized}"
    return f"unsupported executor type：executor_ref={executor_ref}, type={normalized or '<empty>'}"
