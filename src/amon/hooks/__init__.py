"""Hook system for Amon."""

from .loader import load_hook, load_hooks
from .matcher import match
from .runner import process_event
from .types import Hook, HookAction, HookFilter, HookPolicy

__all__ = [
    "Hook",
    "HookAction",
    "HookFilter",
    "HookPolicy",
    "load_hook",
    "load_hooks",
    "match",
    "process_event",
]
