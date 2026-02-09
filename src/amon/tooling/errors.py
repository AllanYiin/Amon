"""Tooling error definitions."""

from __future__ import annotations


class ToolError(RuntimeError):
    """Base class for tooling errors."""


class PolicyDenied(ToolError):
    """Raised when a tool is denied by policy."""


class ApprovalRequired(ToolError):
    """Raised when a tool requires approval before execution."""
