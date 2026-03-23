"""Workspace definition commands."""

from __future__ import annotations

import json
from pathlib import Path

from amon.application import WorkspaceService
from amon.core import AmonCore


def handle_workspace_definitions(core: AmonCore, args) -> None:
    service = WorkspaceService(core, args.project)
    if args.workspace_definitions_command == "list":
        payload = service.list_definitions(args.kind)
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return
    if args.workspace_definitions_command == "get":
        payload = service.get_definition(args.kind, args.entity_id)
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return
    if args.workspace_definitions_command in {"create", "update"}:
        payload = json.loads(Path(args.file).read_text(encoding="utf-8"))
        if args.workspace_definitions_command == "create":
            result = service.create_definition(args.kind, payload)
        else:
            result = service.update_definition(args.kind, args.entity_id, payload)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return
    if args.workspace_definitions_command == "delete":
        result = service.delete_definition(args.kind, args.entity_id)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return
    raise ValueError("請指定 workspace definitions 指令")
