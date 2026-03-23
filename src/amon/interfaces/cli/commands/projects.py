"""Workspace project commands."""

from __future__ import annotations

import json

from amon.application import WorkspaceService
from amon.core import AmonCore


def handle_workspace_projects(core: AmonCore, args) -> None:
    if args.workspace_projects_command != "summary":
        raise ValueError("請指定 workspace projects 指令")
    payload = WorkspaceService(core, args.project).get_project_summary()
    print(json.dumps(payload, ensure_ascii=False, indent=2))
