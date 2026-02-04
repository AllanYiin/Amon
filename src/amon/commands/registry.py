"""Command registry for chat execution."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable


CommandHandler = Callable[..., dict[str, Any]]


@dataclass(frozen=True)
class CommandDefinition:
    name: str
    schema: dict[str, Any]
    handler: CommandHandler

    def to_dict(self) -> dict[str, Any]:
        return {"name": self.name, "schema": self.schema}


_COMMANDS: dict[str, CommandDefinition] = {}


def register_command(name: str, schema: dict[str, Any], handler: CommandHandler) -> CommandDefinition:
    if not name:
        raise ValueError("command name 不可為空")
    if name in _COMMANDS:
        raise ValueError(f"command 已註冊：{name}")
    definition = CommandDefinition(name=name, schema=schema, handler=handler)
    _COMMANDS[name] = definition
    return definition


def list_commands() -> list[dict[str, Any]]:
    return [definition.to_dict() for definition in _COMMANDS.values()]


def get_command(name: str) -> CommandDefinition | None:
    return _COMMANDS.get(name)


def clear_commands() -> None:
    _COMMANDS.clear()
