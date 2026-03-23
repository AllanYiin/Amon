"""Workspace confirmation commands."""

from __future__ import annotations

import json

from amon.application import WorkspaceService
from amon.core import AmonCore


def handle_workspace_confirmations(core: AmonCore, args) -> None:
    service = WorkspaceService(core, args.project)
    if args.workspace_confirmations_command == "list":
        print(json.dumps(service.list_confirmations(run_id=args.run_id), ensure_ascii=False, indent=2))
        return
    if args.workspace_confirmations_command == "approve":
        print(json.dumps(service.resolve_confirmation(args.confirmation_id, approved=True), ensure_ascii=False, indent=2))
        return
    if args.workspace_confirmations_command == "reject":
        print(json.dumps(service.resolve_confirmation(args.confirmation_id, approved=False), ensure_ascii=False, indent=2))
        return
    raise ValueError("請指定 workspace confirmations 指令")
