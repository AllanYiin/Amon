"""Tooling package for internal scaffolding."""

from __future__ import annotations

from importlib import util
from pathlib import Path
import sys

_legacy_path = Path(__file__).resolve().parent.parent / "tooling.py"
_spec = util.spec_from_file_location("amon._tooling_legacy", _legacy_path)
if _spec is None or _spec.loader is None:
    raise ImportError(f"Unable to load legacy tooling module from {_legacy_path}")
_legacy_module = util.module_from_spec(_spec)
sys.modules[_spec.name] = _legacy_module
_spec.loader.exec_module(_legacy_module)

for _name in dir(_legacy_module):
    if _name.startswith("_"):
        continue
    globals()[_name] = getattr(_legacy_module, _name)

from . import types as types  # noqa: E402

__all__ = [name for name in globals() if not name.startswith("_")]
