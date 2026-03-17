from __future__ import annotations

import builtins
import contextlib
import io
import re
import textwrap
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple


REPL_BLOCK_RE = re.compile(
    r"```(?P<lang>[a-zA-Z0-9_+-]*)\n(?P<code>.*?)\n```",
    re.DOTALL,
)


@dataclass
class ReplResult:
    code: str
    stdout: str
    error: Optional[str] = None


class ReplSession:
    """A lightweight persistent Python REPL session.

    Notes:
    - This is *not* a hardened sandbox. For real deployments, run this in a
      container / seccomp jail / separate process with timeouts.
    - In this skill we use it as the execution substrate for RLM-style context
      interaction.
    """

    def __init__(
        self,
        initial_globals: Optional[Dict[str, Any]] = None,
        allowed_builtins: Optional[Dict[str, Any]] = None,
        max_stdout_chars: int = 8_000,
    ):
        self.globals: Dict[str, Any] = dict(initial_globals or {})
        # Expose a conservative default builtins set unless explicitly given.
        if allowed_builtins is None:
            allowed_builtins = {
                "print": print,
                "len": len,
                "range": range,
                "enumerate": enumerate,
                "min": min,
                "max": max,
                "sum": sum,
                "sorted": sorted,
                "list": list,
                "dict": dict,
                "set": set,
                "tuple": tuple,
                "str": str,
                "int": int,
                "float": float,
                "bool": bool,
                "abs": abs,
                "any": any,
                "all": all,
                "zip": zip,
                "map": map,
                "filter": filter,
                "re": __import__("re"),
                "math": __import__("math"),
                "json": __import__("json"),
                "textwrap": __import__("textwrap"),
            }
        self.globals["__builtins__"] = allowed_builtins
        self.max_stdout_chars = max_stdout_chars

    def exec(self, code: str) -> ReplResult:
        buf = io.StringIO()
        err: Optional[str] = None
        with contextlib.redirect_stdout(buf):
            try:
                exec(code, self.globals, self.globals)
            except Exception as e:  # noqa: BLE001
                err = f"{type(e).__name__}: {e}"
        out = buf.getvalue()
        if len(out) > self.max_stdout_chars:
            out = out[: self.max_stdout_chars] + "\n... [stdout truncated]"
        return ReplResult(code=code, stdout=out, error=err)

    def snapshot(self, *, max_items: int = 30) -> str:
        """Return a brief variable listing to help the root model orient."""
        keys = [k for k in self.globals.keys() if not k.startswith("__")]
        keys = sorted(keys)
        shown = keys[:max_items]
        extra = "" if len(keys) <= max_items else f" (+{len(keys)-max_items} more)"
        return ", ".join(shown) + extra


def extract_repl_blocks(text: str, *, allowed_langs: Tuple[str, ...] = ("repl", "python")) -> List[str]:
    """Extract fenced code blocks from an LLM message.

    By default, only blocks labelled ```repl or ```python are executed.
    """
    blocks: List[str] = []
    for m in REPL_BLOCK_RE.finditer(text):
        lang = (m.group("lang") or "").strip().lower()
        code = m.group("code")
        if lang in allowed_langs:
            blocks.append(textwrap.dedent(code).strip() + "\n")
    return blocks


FINAL_RE = re.compile(r"\bFINAL\((?P<content>.*?)\)\s*$", re.DOTALL)
FINAL_VAR_RE = re.compile(r"\bFINAL_VAR\((?P<var>[a-zA-Z_][a-zA-Z0-9_]*)\)\s*$", re.DOTALL)


@dataclass
class FinalAnswer:
    kind: str  # "text" or "var"
    value: str


def parse_final_answer(text: str) -> Optional[FinalAnswer]:
    """Parse FINAL(...) or FINAL_VAR(name) from a model message.

    We intentionally require it to appear near the end to avoid accidental matches.
    """
    t = text.strip()
    m = FINAL_VAR_RE.search(t)
    if m:
        return FinalAnswer(kind="var", value=m.group("var").strip())
    m = FINAL_RE.search(t)
    if m:
        # Strip matching surrounding quotes if present.
        content = m.group("content").strip()
        if (content.startswith('"') and content.endswith('"')) or (
            content.startswith("'") and content.endswith("'")
        ):
            content = content[1:-1]
        return FinalAnswer(kind="text", value=content)
    return None
