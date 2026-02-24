from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from amon.chat.session_store import (
    build_prompt_with_history,
    create_chat_session,
    load_latest_chat_id,
    load_latest_run_context,
    load_recent_dialogue,
)


@dataclass
class ChatTurnBundle:
    chat_id: str
    history: list[dict[str, str]]
    run_context: dict[str, str | None]
    prompt_with_history: str
    router_context: dict[str, Any] | None
    short_continuation: bool


_SESSION_CREATOR = Callable[[str], str]


def assemble_chat_turn(
    *,
    project_id: str,
    chat_id: str | None,
    message: str,
    create_session: _SESSION_CREATOR = create_chat_session,
) -> ChatTurnBundle:
    resolved_chat_id = (chat_id or "").strip()
    if not resolved_chat_id:
        resolved_chat_id = load_latest_chat_id(project_id) or create_session(project_id)

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
