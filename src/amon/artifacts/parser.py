"""Parse artifact code-fence blocks from model responses."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ArtifactBlock:
    """A parsed code-fence artifact block."""

    lang: str
    file_path: str
    content: str
    index: int


def _parse_info_string(info: str) -> tuple[str, str] | None:
    tokens = [token for token in info.strip().split() if token]
    if not tokens:
        return None

    file_token = next((token for token in tokens if token.startswith("file=")), None)
    if not file_token:
        return None
    file_path = file_token[len("file=") :].strip()
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
            if parsed:
                lang, file_path = parsed
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
