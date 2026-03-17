"""Skill archive helpers."""

from __future__ import annotations

from pathlib import Path
import zipfile


def iter_skill_directories(base_dir: Path) -> list[Path]:
    """Return immediate child directories that define a skill."""
    if not base_dir.exists():
        return []
    return sorted(
        child for child in base_dir.iterdir() if child.is_dir() and (child / "SKILL.md").exists()
    )


def build_skill_archive(source_dir: Path, output_path: Path, *, root_name: str | None = None) -> Path:
    """Package a skill directory into a .skill zip archive."""
    skill_file = source_dir / "SKILL.md"
    if not skill_file.exists():
        raise FileNotFoundError(f"找不到 SKILL.md：{skill_file}")

    archive_root = root_name or source_dir.name
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(item for item in source_dir.rglob("*") if item.is_file()):
            arcname = (Path(archive_root) / path.relative_to(source_dir)).as_posix()
            archive.write(path, arcname)
    return output_path
