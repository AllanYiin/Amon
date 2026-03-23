from importlib import import_module
from pathlib import Path

from ...domain.entities import Project


def bootstrap_manifest_storage(project_root: Path, *, project: Project | None = None) -> dict[str, Path]:
    module = import_module("amon.storage.migrations.0001_manifest_v1")
    return module.bootstrap_manifest_storage(project_root, project=project)


__all__ = ["bootstrap_manifest_storage"]
