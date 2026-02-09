"""Filesystem builtin tools."""

from __future__ import annotations

from pathlib import Path
import os
import re
import shutil
from typing import Any

from ..types import ToolCall, ToolResult, ToolSpec


_DEFAULT_MAX_BYTES = 200_000


def spec_filesystem_read() -> ToolSpec:
    return ToolSpec(
        name="filesystem.read",
        description="Read a UTF-8 text file within the workspace. Use for code/config/doc reading.",
        input_schema={
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "max_bytes": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 5_000_000,
                    "default": _DEFAULT_MAX_BYTES,
                },
            },
            "required": ["path"],
            "additionalProperties": False,
        },
        risk="low",
        annotations={"builtin": True},
    )


def handle_filesystem_read(call: ToolCall) -> ToolResult:
    path = call.args.get("path")
    if not isinstance(path, str) or not path:
        return ToolResult(
            content=[{"type": "text", "text": "缺少 path 參數。"}],
            is_error=True,
            meta={"status": "invalid_args"},
        )
    max_bytes = int(call.args.get("max_bytes", _DEFAULT_MAX_BYTES))
    try:
        data = Path(path).read_bytes()
    except OSError as exc:
        return ToolResult(
            content=[{"type": "text", "text": f"讀取檔案失敗：{exc}"}],
            is_error=True,
            meta={"status": "io_error"},
        )
    truncated = len(data) > max_bytes
    if truncated:
        data = data[:max_bytes]
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        text = data.decode("utf-8", errors="replace")
    return ToolResult(
        content=[{"type": "text", "text": text}],
        meta={"truncated": truncated, "bytes": len(data)},
    )


def spec_filesystem_list() -> ToolSpec:
    return ToolSpec(
        name="filesystem.list",
        description="List directory entries within the workspace.",
        input_schema={
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "max_entries": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 10_000,
                    "default": 500,
                },
                "include_hidden": {"type": "boolean", "default": False},
            },
            "required": ["path"],
            "additionalProperties": False,
        },
        risk="low",
        annotations={"builtin": True},
    )


def handle_filesystem_list(call: ToolCall) -> ToolResult:
    path = call.args.get("path")
    if not isinstance(path, str) or not path:
        return ToolResult(
            content=[{"type": "text", "text": "缺少 path 參數。"}],
            is_error=True,
            meta={"status": "invalid_args"},
        )
    max_entries = int(call.args.get("max_entries", 500))
    include_hidden = bool(call.args.get("include_hidden", False))
    items: list[dict[str, Any]] = []
    try:
        for name in sorted(os.listdir(path)):
            if not include_hidden and name.startswith("."):
                continue
            full = os.path.join(path, name)
            items.append(
                {"name": name, "type": "dir" if os.path.isdir(full) else "file"}
            )
            if len(items) >= max_entries:
                break
    except FileNotFoundError:
        return ToolResult(
            content=[{"type": "text", "text": f"找不到目錄：{path}"}],
            is_error=True,
            meta={"status": "not_found"},
        )
    except OSError as exc:
        return ToolResult(
            content=[{"type": "text", "text": f"列出目錄失敗：{exc}"}],
            is_error=True,
            meta={"status": "io_error"},
        )
    lines = [f"{item['type']}\t{item['name']}" for item in items]
    return ToolResult(
        content=[{"type": "text", "text": "\n".join(lines)}],
        meta={"count": len(items)},
    )


def spec_filesystem_glob() -> ToolSpec:
    return ToolSpec(
        name="filesystem.glob",
        description="Return paths under a root matching a glob pattern.",
        input_schema={
            "type": "object",
            "properties": {
                "root": {"type": "string"},
                "pattern": {"type": "string", "default": "**/*"},
                "max_entries": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 50_000,
                    "default": 2000,
                },
                "include_hidden": {"type": "boolean", "default": False},
            },
            "required": ["root"],
            "additionalProperties": False,
        },
        risk="low",
        annotations={"builtin": True},
    )


def handle_filesystem_glob(call: ToolCall) -> ToolResult:
    root = call.args.get("root")
    if not isinstance(root, str) or not root:
        return ToolResult(
            content=[{"type": "text", "text": "缺少 root 參數。"}],
            is_error=True,
            meta={"status": "invalid_args"},
        )
    pattern = call.args.get("pattern", "**/*")
    max_entries = int(call.args.get("max_entries", 2000))
    include_hidden = bool(call.args.get("include_hidden", False))
    root_path = Path(root)
    if not root_path.exists():
        return ToolResult(
            content=[{"type": "text", "text": f"找不到路徑：{root}"}],
            is_error=True,
            meta={"status": "not_found"},
        )
    matches: list[str] = []
    try:
        for path in root_path.glob(pattern):
            rel = path.relative_to(root_path).as_posix()
            if not include_hidden and any(part.startswith(".") for part in path.parts):
                continue
            matches.append(rel)
            if len(matches) >= max_entries:
                break
    except OSError as exc:
        return ToolResult(
            content=[{"type": "text", "text": f"Glob 失敗：{exc}"}],
            is_error=True,
            meta={"status": "io_error"},
        )
    return ToolResult(
        content=[{"type": "text", "text": "\n".join(matches)}],
        meta={"count": len(matches)},
    )


def spec_filesystem_grep() -> ToolSpec:
    return ToolSpec(
        name="filesystem.grep",
        description="Search for a regex pattern in files under a root directory (workspace-bounded).",
        input_schema={
            "type": "object",
            "properties": {
                "root": {"type": "string"},
                "pattern": {"type": "string"},
                "file_glob": {"type": "string", "default": "**/*"},
                "max_hits": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 50_000,
                    "default": 2000,
                },
            },
            "required": ["root", "pattern"],
            "additionalProperties": False,
        },
        risk="low",
        annotations={"builtin": True},
    )


def handle_filesystem_grep(call: ToolCall) -> ToolResult:
    root = call.args.get("root")
    pattern = call.args.get("pattern")
    if not isinstance(root, str) or not root:
        return ToolResult(
            content=[{"type": "text", "text": "缺少 root 參數。"}],
            is_error=True,
            meta={"status": "invalid_args"},
        )
    if not isinstance(pattern, str) or not pattern:
        return ToolResult(
            content=[{"type": "text", "text": "缺少 pattern 參數。"}],
            is_error=True,
            meta={"status": "invalid_args"},
        )
    file_glob = call.args.get("file_glob", "**/*")
    max_hits = int(call.args.get("max_hits", 2000))

    try:
        rx = re.compile(pattern)
    except re.error as exc:
        return ToolResult(
            content=[{"type": "text", "text": f"無效的正則表達式：{exc}"}],
            is_error=True,
            meta={"status": "invalid_pattern"},
        )

    hits: list[str] = []
    for dirpath, _, filenames in os.walk(os.path.expanduser(root)):
        for filename in filenames:
            full = os.path.join(dirpath, filename)
            rel = os.path.relpath(full, root).replace(os.sep, "/")
            if file_glob not in ("**/*", "*"):
                if file_glob.startswith("*.") and not filename.endswith(file_glob[1:]):
                    continue
            try:
                data = Path(full).read_bytes()[:2_000_000]
                text = data.decode("utf-8", errors="ignore")
            except OSError:
                continue
            for lineno, line in enumerate(text.splitlines(), start=1):
                if rx.search(line):
                    hits.append(f"{rel}:{lineno}:{line[:300]}")
                    if len(hits) >= max_hits:
                        return ToolResult(
                            content=[{"type": "text", "text": "\n".join(hits)}],
                            meta={"truncated": True, "hits": len(hits)},
                        )
    return ToolResult(
        content=[{"type": "text", "text": "\n".join(hits)}],
        meta={"truncated": False, "hits": len(hits)},
    )


def spec_filesystem_write() -> ToolSpec:
    return ToolSpec(
        name="filesystem.write",
        description="Write UTF-8 text content to a file (create if missing).",
        input_schema={
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "content": {"type": "string"},
                "append": {"type": "boolean", "default": False},
                "encoding": {"type": "string", "default": "utf-8"},
            },
            "required": ["path", "content"],
            "additionalProperties": False,
        },
        risk="medium",
        annotations={"builtin": True},
    )


def handle_filesystem_write(call: ToolCall) -> ToolResult:
    path = call.args.get("path")
    content = call.args.get("content")
    if not isinstance(path, str) or not path:
        return ToolResult(
            content=[{"type": "text", "text": "缺少 path 參數。"}],
            is_error=True,
            meta={"status": "invalid_args"},
        )
    if not isinstance(content, str):
        return ToolResult(
            content=[{"type": "text", "text": "缺少 content 參數。"}],
            is_error=True,
            meta={"status": "invalid_args"},
        )
    append = bool(call.args.get("append", False))
    encoding = str(call.args.get("encoding", "utf-8"))
    mode = "a" if append else "w"
    try:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with Path(path).open(mode, encoding=encoding) as handle:
            handle.write(content)
    except OSError as exc:
        return ToolResult(
            content=[{"type": "text", "text": f"寫入檔案失敗：{exc}"}],
            is_error=True,
            meta={"status": "io_error"},
        )
    return ToolResult(content=[{"type": "text", "text": f"已寫入：{path}"}])


def spec_filesystem_patch() -> ToolSpec:
    return ToolSpec(
        name="filesystem.patch",
        description="Apply a unified diff patch to a UTF-8 text file.",
        input_schema={
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "diff": {"type": "string"},
            },
            "required": ["path", "diff"],
            "additionalProperties": False,
        },
        risk="medium",
        annotations={"builtin": True},
    )


def handle_filesystem_patch(call: ToolCall) -> ToolResult:
    path = call.args.get("path")
    diff = call.args.get("diff")
    if not isinstance(path, str) or not path:
        return ToolResult(
            content=[{"type": "text", "text": "缺少 path 參數。"}],
            is_error=True,
            meta={"status": "invalid_args"},
        )
    if not isinstance(diff, str) or not diff:
        return ToolResult(
            content=[{"type": "text", "text": "缺少 diff 參數。"}],
            is_error=True,
            meta={"status": "invalid_args"},
        )
    try:
        original_text = Path(path).read_text(encoding="utf-8")
    except FileNotFoundError:
        original_text = ""
    except OSError as exc:
        return ToolResult(
            content=[{"type": "text", "text": f"讀取檔案失敗：{exc}"}],
            is_error=True,
            meta={"status": "io_error"},
        )
    try:
        updated_text = _apply_unified_diff(original_text, diff)
    except ValueError as exc:
        return ToolResult(
            content=[{"type": "text", "text": f"套用 patch 失敗：{exc}"}],
            is_error=True,
            meta={"status": "patch_failed"},
        )
    try:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        Path(path).write_text(updated_text, encoding="utf-8")
    except OSError as exc:
        return ToolResult(
            content=[{"type": "text", "text": f"寫入檔案失敗：{exc}"}],
            is_error=True,
            meta={"status": "io_error"},
        )
    return ToolResult(content=[{"type": "text", "text": f"已套用 patch：{path}"}])


def spec_filesystem_delete() -> ToolSpec:
    return ToolSpec(
        name="filesystem.delete",
        description="Delete a file or directory (optionally move to trash).",
        input_schema={
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "trash": {"type": "boolean", "default": True},
            },
            "required": ["path"],
            "additionalProperties": False,
        },
        risk="high",
        annotations={"builtin": True},
    )


def handle_filesystem_delete(call: ToolCall) -> ToolResult:
    path = call.args.get("path")
    if not isinstance(path, str) or not path:
        return ToolResult(
            content=[{"type": "text", "text": "缺少 path 參數。"}],
            is_error=True,
            meta={"status": "invalid_args"},
        )
    trash = bool(call.args.get("trash", True))
    target = Path(path)
    if not target.exists():
        return ToolResult(
            content=[{"type": "text", "text": f"找不到路徑：{path}"}],
            is_error=True,
            meta={"status": "not_found"},
        )
    try:
        if trash:
            trash_dir = Path(os.environ.get("AMON_HOME", "~/.amon")).expanduser() / "trash"
            trash_dir.mkdir(parents=True, exist_ok=True)
            destination = trash_dir / f"{target.name}.deleted"
            shutil.move(str(target), destination)
            message = f"已移至垃圾桶：{destination}"
        else:
            if target.is_dir():
                shutil.rmtree(target)
            else:
                target.unlink()
            message = f"已刪除：{path}"
    except OSError as exc:
        return ToolResult(
            content=[{"type": "text", "text": f"刪除失敗：{exc}"}],
            is_error=True,
            meta={"status": "io_error"},
        )
    return ToolResult(content=[{"type": "text", "text": message}])


def register_filesystem_tools(registry: Any) -> None:
    registry.register(spec_filesystem_read(), handle_filesystem_read)
    registry.register(spec_filesystem_list(), handle_filesystem_list)
    registry.register(spec_filesystem_glob(), handle_filesystem_glob)
    registry.register(spec_filesystem_grep(), handle_filesystem_grep)
    registry.register(spec_filesystem_write(), handle_filesystem_write)
    registry.register(spec_filesystem_patch(), handle_filesystem_patch)
    registry.register(spec_filesystem_delete(), handle_filesystem_delete)


def _apply_unified_diff(original_text: str, diff_text: str) -> str:
    lines = diff_text.splitlines()
    if not any(line.startswith("@@") for line in lines):
        raise ValueError("diff 缺少 hunks")
    original_lines = original_text.splitlines()
    trailing_newline = original_text.endswith("\n")
    result_lines: list[str] = []
    idx = 0
    hunk_pattern = re.compile(r"@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")

    i = 0
    while i < len(lines):
        line = lines[i]
        if not line.startswith("@@"):
            i += 1
            continue
        match = hunk_pattern.match(line)
        if not match:
            raise ValueError("無效的 hunk 標頭")
        start_old = int(match.group(1))
        count_old = int(match.group(2) or "1")
        i += 1
        start_index = start_old - 1
        if start_index < idx:
            raise ValueError("hunk 重疊或順序錯誤")
        result_lines.extend(original_lines[idx:start_index])
        idx = start_index
        removed = 0
        added = 0
        while i < len(lines) and not lines[i].startswith("@@"):
            hunk_line = lines[i]
            if hunk_line.startswith(" "):
                expected = hunk_line[1:]
                if idx >= len(original_lines) or original_lines[idx] != expected:
                    raise ValueError("上下文不匹配")
                result_lines.append(expected)
                idx += 1
            elif hunk_line.startswith("-"):
                expected = hunk_line[1:]
                if idx >= len(original_lines) or original_lines[idx] != expected:
                    raise ValueError("移除內容不匹配")
                idx += 1
                removed += 1
            elif hunk_line.startswith("+"):
                result_lines.append(hunk_line[1:])
                added += 1
            i += 1
        if removed != count_old:
            remaining = count_old - removed
            idx += max(0, remaining)
    result_lines.extend(original_lines[idx:])
    result_text = "\n".join(result_lines)
    if trailing_newline:
        result_text += "\n"
    return result_text
