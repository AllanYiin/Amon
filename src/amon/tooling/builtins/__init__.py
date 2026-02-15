"""Builtin tool specs and handlers."""

from .artifacts import register_artifacts_tools
from .audit_tools import register_audit_tools
from .filesystem import register_filesystem_tools
from .memory import register_memory_tools
from .process import register_process_tools
from .terminal import register_terminal_tools
from .web import register_web_tools

__all__ = [
    "register_artifacts_tools",
    "register_audit_tools",
    "register_filesystem_tools",
    "register_memory_tools",
    "register_process_tools",
    "register_terminal_tools",
    "register_web_tools",
]
