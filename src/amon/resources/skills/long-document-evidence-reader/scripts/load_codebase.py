from __future__ import annotations

import os
from pathlib import Path
from typing import Iterable, List, Optional, Sequence, Set

from context_store import Chunk, ContextStore


DEFAULT_TEXT_EXTS: Set[str] = {
    ".py",
    ".ipynb",
    ".js",
    ".ts",
    ".tsx",
    ".jsx",
    ".java",
    ".go",
    ".rs",
    ".cpp",
    ".c",
    ".h",
    ".cs",
    ".php",
    ".rb",
    ".swift",
    ".kt",
    ".scala",
    ".sql",
    ".md",
    ".rst",
    ".toml",
    ".yaml",
    ".yml",
    ".json",
    ".ini",
    ".cfg",
    ".txt",
    ".env",
    ".sh",
    ".dockerfile",
}


def _is_binary(path: Path) -> bool:
    # Simple heuristic: look for NUL byte in the first chunk
    try:
        with open(path, "rb") as f:
            head = f.read(4096)
        return b"\x00" in head
    except Exception:
        return True


def load_codebase(
    repo_root: str,
    *,
    include_exts: Optional[Sequence[str]] = None,
    exclude_dirs: Sequence[str] = (".git", ".hg", ".svn", "node_modules", "dist", "build", "__pycache__"),
    max_file_bytes: int = 2_000_000,
    add_line_numbers: bool = True,
    encoding: str = "utf-8",
) -> ContextStore:
    """Load a code repository into a ContextStore.

    Each file becomes one chunk.

    - Skips binary files.
    - Skips huge files by size.
    - Optionally adds line numbers to make citations stable.
    """

    root = Path(repo_root).expanduser().resolve()
    if not root.exists() or not root.is_dir():
        raise FileNotFoundError(f"Repo root not found or not a dir: {root}")

    exts: Set[str] = set(e.lower() for e in (include_exts or DEFAULT_TEXT_EXTS))
    exclude_dirs_set = set(exclude_dirs)

    chunks: List[Chunk] = []

    for dirpath, dirnames, filenames in os.walk(root):
        # mutate dirnames in-place to prune
        dirnames[:] = [d for d in dirnames if d not in exclude_dirs_set]

        for fn in filenames:
            path = Path(dirpath) / fn
            rel = path.relative_to(root).as_posix()

            # Extension filtering
            ext = path.suffix.lower()
            if ext and ext not in exts:
                # Support special files like Dockerfile
                if path.name.lower() != "dockerfile":
                    continue

            try:
                size = path.stat().st_size
            except Exception:
                continue

            if size > max_file_bytes:
                continue

            if _is_binary(path):
                continue

            try:
                text = path.read_text(encoding=encoding, errors="replace")
            except Exception:
                continue

            if add_line_numbers:
                lines = text.splitlines()
                text = "\n".join(f"{i+1:>6}  {line}" for i, line in enumerate(lines))

            header = f"# FILE: {rel}\n"
            chunks.append(Chunk(source=f"file:{rel}", text=header + text))

    # Sort for determinism
    chunks.sort(key=lambda c: c.source)

    return ContextStore(chunks=chunks, name=root.name)

