"""Workspace run commands."""

from __future__ import annotations

import json
import time

from amon.application import WorkspaceService
from amon.core import AmonCore


def handle_workspace_runs(core: AmonCore, args) -> None:
    service = WorkspaceService(core, args.project)
    if args.workspace_runs_command == "list":
        print(json.dumps(service.list_runs(), ensure_ascii=False, indent=2))
        return
    if args.workspace_runs_command == "get":
        print(json.dumps(service.get_run(args.run_id), ensure_ascii=False, indent=2))
        return
    if args.workspace_runs_command == "create":
        result = service.create_run(
            workflow_ref=args.workflow,
            template_ref=args.template,
            variables=json.loads(args.variables),
            notes=args.notes,
        )
        if args.execute:
            queued = service.enqueue_run(result["run"]["id"])
            result["run"] = queued
            core.run_graph(
                project_path=service.project_root,
                graph_path=service.project_root / ".amon" / "runs" / queued["id"] / "compiled.taskgraph.v3.json",
                variables=result["variables"],
                run_id=queued["id"],
            )
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return
    if args.workspace_runs_command == "resume":
        result = service.resume_run(args.run_id)
        if args.execute:
            core.run_graph(
                project_path=service.project_root,
                graph_path=service.project_root / ".amon" / "runs" / args.run_id / "compiled.taskgraph.v3.json",
                variables=result["variables"],
                run_id=args.run_id,
            )
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return
    if args.workspace_runs_command == "cancel":
        print(json.dumps(service.cancel_run(args.run_id), ensure_ascii=False, indent=2))
        return
    if args.workspace_runs_command == "archive":
        print(json.dumps(service.archive_run(args.run_id), ensure_ascii=False, indent=2))
        return
    if args.workspace_runs_command == "stream":
        _stream_run(service, args.run_id, follow=args.follow)
        return
    raise ValueError("請指定 workspace runs 指令")


def _stream_run(service: WorkspaceService, run_id: str, *, follow: bool) -> None:
    sent = 0
    idle_rounds = 0
    while True:
        payload = service.get_run(run_id)
        events = payload.get("events") if isinstance(payload, dict) else []
        if not isinstance(events, list):
            events = []
        if sent < len(events):
            for event in events[sent:]:
                event_name = str(event.get("event") or event.get("type") or "message").strip()
                if event_name == "node.chunk":
                    print(str(event.get("text") or ""), end="", flush=True)
                else:
                    print(json.dumps(event, ensure_ascii=False))
            sent = len(events)
            idle_rounds = 0
        else:
            idle_rounds += 1
        status = str((payload.get("run") or {}).get("status") or "").strip().lower()
        if status in {"succeeded", "failed", "cancelled", "rolled_back", "archived"} and sent >= len(events):
            if events and str(events[-1].get("event") or "") == "node.chunk":
                print()
            return
        if not follow and idle_rounds >= 1:
            if events and str(events[-1].get("event") or "") == "node.chunk":
                print()
            return
        time.sleep(0.25)
