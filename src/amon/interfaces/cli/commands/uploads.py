"""Workspace upload commands."""

from __future__ import annotations

import json

from amon.application import WorkspaceService
from amon.core import AmonCore


def handle_workspace_uploads(core: AmonCore, args) -> None:
    service = WorkspaceService(core, args.project)
    if args.workspace_uploads_command == "list":
        print(json.dumps(service.list_uploads(), ensure_ascii=False, indent=2))
        return
    if args.workspace_uploads_command == "add":
        print(json.dumps(service.create_upload(args.path, notes=args.notes), ensure_ascii=False, indent=2))
        return
    if args.workspace_uploads_command == "get":
        print(json.dumps(service.get_upload(args.asset_id), ensure_ascii=False, indent=2))
        return
    if args.workspace_uploads_command == "preview":
        print(json.dumps(service.get_upload_preview(args.asset_id), ensure_ascii=False, indent=2))
        return
    if args.workspace_uploads_command == "delete":
        print(json.dumps(service.delete_upload(args.asset_id), ensure_ascii=False, indent=2))
        return
    raise ValueError("請指定 workspace uploads 指令")
