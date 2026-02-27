"""Parse artifact code-fence blocks from model responses."""

from __future__ import annotations

from dataclasses import dataclass
import re


@dataclass(frozen=True)
class ArtifactBlock:
    """A parsed code-fence artifact block."""

    lang: str
    file_path: str
    content: str
    index: int


_FILE_TOKEN_PATTERNS = ("file=", "filename=", "path=")


def _extract_declared_path_from_header(content: str) -> str | None:
    first_line = content.splitlines()[0] if content.splitlines() else ""
    pattern = re.compile(r"(?:<!--|//)\s*(?:filename|path)\s*:\s*([^\s>]+)", re.IGNORECASE)
    matched = pattern.search(first_line.strip())
    if not matched:
        return None
    file_path = matched.group(1).strip()
    if not file_path or any(char in file_path for char in {'"', "'"}):
        return None
    return file_path


def _parse_info_string(info: str) -> tuple[str, str] | None:
    tokens = [token for token in info.strip().split() if token]
    if not tokens:
        return None

    file_token = next((token for token in tokens if token.startswith(_FILE_TOKEN_PATTERNS)), None)
    if not file_token:
        return None
    token_key, _, token_value = file_token.partition("=")
    if token_key not in {"file", "filename", "path"}:
        return None
    file_path = token_value.strip()
    if not file_path:
        return None
    if any(char in file_path for char in {'"', "'"}):
        return None

    lang = ""
    for token in tokens:
        if token == file_token:
            continue
        if "=" in token:
            continue
        lang = token
        break
    return lang, file_path


def parse_artifact_blocks(text: str) -> list[ArtifactBlock]:
    """Return fenced code blocks that include a `file=` info-string token."""

    blocks: list[ArtifactBlock] = []
    lines = text.splitlines(keepends=True)
    in_fence = False
    info = ""
    content_lines: list[str] = []
    block_index = 0

    for line in lines:
        stripped = line.strip()
        if not in_fence:
            if stripped.startswith("```"):
                in_fence = True
                info = stripped[3:].strip()
                content_lines = []
            continue

        if stripped == "```":
            parsed = _parse_info_string(info)
            resolved = parsed if parsed else ("", _extract_declared_path_from_header("".join(content_lines)))
            if resolved and resolved[1]:
                lang, file_path = resolved
                blocks.append(
                    ArtifactBlock(
                        lang=lang,
                        file_path=file_path,
                        content="".join(content_lines),
                        index=block_index,
                    )
                )
                block_index += 1
            in_fence = False
            info = ""
            content_lines = []
            continue

        content_lines.append(line)

    return blocks
