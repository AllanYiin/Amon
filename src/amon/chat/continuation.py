from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from amon.chat.session_store import (
    build_prompt_with_history,
    ensure_chat_session,
    chat_session_exists,
    load_latest_run_context,
    load_recent_dialogue,
)
from amon.logging import log_event


@dataclass
class ChatTurnBundle:
    chat_id: str
    history: list[dict[str, str]]
    run_context: dict[str, str | None]
    prompt_with_history: str
    router_context: dict[str, Any] | None
    short_continuation: bool
    chat_id_source: str


_SESSION_ENSURER = Callable[[str, str | None], tuple[str, str]]


def assemble_chat_turn(
    *,
    project_id: str,
    chat_id: str | None,
    message: str,
    ensure_session: _SESSION_ENSURER = ensure_chat_session,
) -> ChatTurnBundle:
    incoming_chat_id = (chat_id or "").strip()
    resolved_chat_id, chat_id_source = ensure_session(project_id, incoming_chat_id or None)

    if incoming_chat_id and incoming_chat_id != resolved_chat_id and not chat_session_exists(project_id, incoming_chat_id):
        log_event(
            {
                "level": "WARNING",
                "event": "chat_session_fallback",
                "project_id": project_id,
                "incoming_chat_id": incoming_chat_id,
                "fallback_chat_id": resolved_chat_id,
                "reason": "incoming_chat_id_not_found",
            }
        )

    history = load_recent_dialogue(project_id, resolved_chat_id)
    run_context = load_latest_run_context(project_id, resolved_chat_id)
    prompt_with_history = build_prompt_with_history(message, history)
    router_context = {"conversation_history": history} if history else None
    short_continuation = is_short_continuation_message(message) and bool(history)

    return ChatTurnBundle(
        chat_id=resolved_chat_id,
        history=history,
        run_context=run_context,
        prompt_with_history=prompt_with_history,
        router_context=router_context,
        short_continuation=short_continuation,
        chat_id_source=chat_id_source,
    )


def is_short_continuation_message(message: str) -> bool:
    normalized = " ".join((message or "").split())
    if not normalized:
        return False
    if len(normalized) <= 20:
        return True
    if len(normalized) <= 32 and " " not in normalized:
        return True
    return False
