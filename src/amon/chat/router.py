"""Intent router for chat messages."""

from __future__ import annotations

from typing import Any

from amon.commands.registry import ensure_default_commands_initialized, list_commands
from amon.config import ConfigLoader

from .policy_guard import apply_policy_guard
from .router_llm import LLMClient, route_with_llm
from .router_types import RouterResult


def route_intent(
    message: str,
    project_id: str | None = None,
    run_id: str | None = None,
    context: dict[str, Any] | None = None,
    llm_client: LLMClient | None = None,
) -> RouterResult:
    ensure_default_commands_initialized()

    if message is None:
        message = ""

    merged_context = dict(context or {})
    if project_id:
        merged_context.setdefault("project_id", project_id)
    if run_id:
        merged_context.setdefault("run_id", run_id)

    commands_registry = list_commands()
    llm_result = route_with_llm(
        message,
        context=merged_context,
        commands_registry=commands_registry,
        project_id=project_id,
        llm_client=llm_client,
    )
    config = ConfigLoader().resolve(project_id=project_id).effective
    allowed_paths = config.get("tools", {}).get("allowed_paths", [])
    return apply_policy_guard(
        llm_result,
        commands_registry=commands_registry,
        allowed_paths=allowed_paths,
    )
