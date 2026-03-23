"""Stage 6 workspace orchestration over manifest v1 storage and taskgraph runtime."""

from __future__ import annotations

import json
import re
import uuid
from pathlib import Path
from typing import Any

from amon.core import AmonCore
from amon.domain import (
    AgentProfile,
    AmonManifest,
    ExecutorBinding,
    ManifestProject,
    Project,
    RunRecord,
    TaskDefinition,
    Template,
    ToolPolicy,
    WorkflowDefinition,
)
from amon.planning import bind_workflow, compile_manifest_workflow
from amon.runtime_vnext import ConfirmationQueue, ResumeService
from amon.storage import DefinitionRepository, ProjectRepository, RunRepository, UploadRepository
from amon.templates import TemplateLibrary, instantiate_builtin_template

from .preview_service import PreviewService
from .ui_state_service import UIStateService
from .upload_service import UploadService


DEFINITION_KIND_MAP = {
    "tasks": ("tasks", TaskDefinition),
    "agents": ("agents", AgentProfile),
    "executors": ("executors", ExecutorBinding),
    "workflows": ("workflows", WorkflowDefinition),
    "templates": ("templates", Template),
    "tool-policies": ("tool_policies", ToolPolicy),
}
TERMINAL_RUN_STATUSES = {"succeeded", "failed", "cancelled", "rolled_back", "archived"}


class WorkspaceService:
    def __init__(self, core: AmonCore, project_id: str) -> None:
        self.core = core
        self.project_id = str(project_id or "").strip()
        self.project_root = self.core.get_project_path(self.project_id)
        self.project_repo = ProjectRepository(self.project_root)
        self.definition_repo = DefinitionRepository(self.project_root)
        self.run_repo = RunRepository(self.project_root)
        self.upload_repo = UploadRepository(self.project_root)
        self.upload_service = UploadService(self.project_root)
        self.preview_service = PreviewService(self.project_root)
        self.ui_state_service = UIStateService(self.project_root)
        self.resume_service = ResumeService(self.project_root)
        self.confirmation_queue = ConfirmationQueue(self.project_root)
        self.template_library = TemplateLibrary()
        self._ensure_project_synced()

    def list_projects(self, *, include_deleted: bool = False) -> list[dict[str, Any]]:
        return [record.to_dict() for record in self.core.list_projects(include_deleted=include_deleted)]

    def get_project_summary(self) -> dict[str, Any]:
        project = self.project_repo.load()
        ui_state = self.ui_state_service.load()
        runs = sorted(self.run_repo.list(), key=lambda item: item.updated_at, reverse=True)
        uploads = sorted(self.upload_repo.list(), key=lambda item: item.updated_at, reverse=True)
        resumable = [run.to_dict() for run in runs if run.status in {"queued", "running", "waiting_confirmation", "paused", "retrying"}]
        recent_preview = next((asset.to_dict() for asset in uploads if asset.preview_ref or asset.metadata), None)
        pending_confirmations = self.list_confirmations()
        return {
            "project": project.to_dict(),
            "ui_state": ui_state,
            "recent_run": runs[0].to_dict() if runs else None,
            "resumable_runs": resumable,
            "pending_confirmations": pending_confirmations,
            "recent_preview": recent_preview,
            "definition_counts": {
                kind: len(self.definition_repo.list(entity_type))
                for kind, (entity_type, _) in DEFINITION_KIND_MAP.items()
            },
        }

    def list_definitions(self, kind: str) -> list[dict[str, Any]]:
        entity_type, _ = self._resolve_definition_kind(kind)
        return [entity.to_dict() for entity in self.definition_repo.list(entity_type)]

    def get_definition(self, kind: str, entity_id: str) -> dict[str, Any]:
        entity_type, _ = self._resolve_definition_kind(kind)
        return self.definition_repo.get(entity_type, entity_id).to_dict()

    def create_definition(self, kind: str, payload: dict[str, Any]) -> dict[str, Any]:
        entity_type, entity_cls = self._resolve_definition_kind(kind)
        entity_payload = dict(payload or {})
        entity_payload["id"] = str(entity_payload.get("id") or self._generate_entity_id(kind, entity_payload)).strip()
        entity = entity_cls.from_dict(entity_payload)
        return self.definition_repo.save(entity_type, entity).to_dict()

    def update_definition(self, kind: str, entity_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        entity_type, _ = self._resolve_definition_kind(kind)
        entity = self.definition_repo.get(entity_type, entity_id)
        entity.update(**dict(payload or {}))
        return self.definition_repo.save(entity_type, entity).to_dict()

    def delete_definition(self, kind: str, entity_id: str) -> dict[str, Any]:
        entity_type, _ = self._resolve_definition_kind(kind)
        return self.definition_repo.soft_delete(entity_type, entity_id).to_dict()

    def create_run(
        self,
        *,
        workflow_ref: str | None = None,
        template_ref: str | None = None,
        variables: dict[str, Any] | None = None,
        labels: list[str] | None = None,
        notes: str | None = None,
        pin: bool = False,
    ) -> dict[str, Any]:
        selected_workflow = str(workflow_ref or "").strip() or None
        selected_template = str(template_ref or "").strip() or None
        if not selected_workflow and not selected_template:
            raise ValueError("請提供 workflow_ref 或 template_ref")

        run_id = f"run-{uuid.uuid4().hex}"
        runtime_vars = dict(variables or {})
        snapshot_manifest: dict[str, Any]
        compiled_graph: dict[str, Any]
        snapshot_refs: dict[str, Any] = {}

        if selected_workflow:
            manifest, compile_result = self._compile_manifest_workflow(selected_workflow)
            snapshot_manifest = manifest.to_dict()
            compiled_graph = compile_result.compiled_graph
            snapshot_refs = {key: pin.to_dict() for key, pin in compile_result.snapshot_pins.items()}
        else:
            snapshot_manifest, compiled_graph = self._compile_template_run(selected_template or "", runtime_vars)
            snapshot_refs = {"template": {"ref": selected_template, "version": 1, "kind": "template"}}

        run = RunRecord.create(
            run_id=run_id,
            workflow_ref=selected_workflow,
            template_ref=selected_template,
            status="compiled",
            snapshot_refs=snapshot_refs,
            metadata={"variables": runtime_vars},
            labels=labels,
            pin=pin,
            notes=notes,
        )
        self.run_repo.create(run, snapshot_manifest=snapshot_manifest, compiled_graph=compiled_graph)
        self.ui_state_service.update_recent_run(run_id)
        return {
            "run": run.to_dict(),
            "graph_path": str(self.project_root / ".amon" / "runs" / run_id / "compiled.taskgraph.v3.json"),
            "variables": runtime_vars,
            "compiled_graph": compiled_graph,
        }

    def enqueue_run(self, run_id: str) -> dict[str, Any]:
        run = self.run_repo.get(run_id)
        run.mark_status("queued")
        self.run_repo.save(run)
        return run.to_dict()

    def get_run(self, run_id: str) -> dict[str, Any]:
        run = self.run_repo.get(run_id)
        return {
            "run": run.to_dict(),
            "checkpoint": self.run_repo.load_checkpoint_metadata(run_id),
            "confirmations": self.run_repo.load_pending_confirmations(run_id),
            "snapshot_manifest": self.run_repo.load_snapshot_manifest(run_id),
            "compiled_graph": self.run_repo.load_compiled_graph(run_id),
            "events": self.list_run_events(run_id),
        }

    def list_runs(self) -> list[dict[str, Any]]:
        return [run.to_dict() for run in sorted(self.run_repo.list(), key=lambda item: item.updated_at, reverse=True)]

    def list_run_events(self, run_id: str) -> list[dict[str, Any]]:
        events_path = self.project_root / ".amon" / "runs" / run_id / "events.jsonl"
        if not events_path.exists():
            return []
        events: list[dict[str, Any]] = []
        for raw in events_path.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line:
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(payload, dict):
                events.append(payload)
        return events

    def resume_run(self, run_id: str) -> dict[str, Any]:
        bundle = self.resume_service.restore_run(run_id)
        run = bundle.run
        if run.status in TERMINAL_RUN_STATUSES:
            raise ValueError(f"此 run 已結束，無法 resume：status={run.status}")
        run.mark_status("queued")
        self.run_repo.save(run)
        return {
            "run": run.to_dict(),
            "checkpoint": bundle.checkpoint,
            "confirmations": bundle.confirmations,
            "graph_path": str(self.project_root / ".amon" / "runs" / run_id / "compiled.taskgraph.v3.json"),
            "variables": dict(run.metadata.get("variables") or {}),
        }

    def cancel_run(self, run_id: str) -> dict[str, Any]:
        run = self.run_repo.get(run_id)
        run.mark_status("cancelled")
        return self.run_repo.save(run).to_dict()

    def archive_run(self, run_id: str) -> dict[str, Any]:
        run = self.run_repo.get(run_id)
        run.archive()
        return self.run_repo.save(run).to_dict()

    def create_upload(self, source_path: str, *, notes: str | None = None) -> dict[str, Any]:
        asset = self.upload_service.create_upload(Path(source_path), notes=notes)
        self.ui_state_service.update_recent_preview(asset.id)
        return asset.to_dict()

    def list_uploads(self) -> list[dict[str, Any]]:
        return [asset.to_dict() for asset in sorted(self.upload_repo.list(), key=lambda item: item.updated_at, reverse=True)]

    def get_upload(self, asset_id: str) -> dict[str, Any]:
        return self.upload_repo.get(asset_id).to_dict()

    def get_upload_preview(self, asset_id: str) -> dict[str, Any]:
        payload = self.preview_service.build_preview_payload(asset_id)
        self.ui_state_service.update_recent_preview(asset_id)
        return payload

    def update_upload(self, asset_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        asset = self.upload_repo.get(asset_id)
        asset.update(**dict(payload or {}))
        return self.upload_repo.save(asset).to_dict()

    def delete_upload(self, asset_id: str) -> dict[str, Any]:
        return self.upload_repo.soft_delete(asset_id).to_dict()

    def list_confirmations(self, *, run_id: str | None = None) -> list[dict[str, Any]]:
        run_ids = [run_id] if run_id else [run.id for run in self.run_repo.list()]
        confirmations: list[dict[str, Any]] = []
        for current_run_id in run_ids:
            confirmations.extend(self.run_repo.load_pending_confirmations(current_run_id))
        return sorted(confirmations, key=lambda item: str(item.get("created_at") or ""), reverse=True)

    def resolve_confirmation(self, confirmation_id: str, *, approved: bool) -> dict[str, Any]:
        for run in self.run_repo.list():
            for item in self.run_repo.load_pending_confirmations(run.id):
                if str(item.get("id") or "") == confirmation_id:
                    return self.confirmation_queue.resolve(run.id, confirmation_id, approved=approved)
        raise KeyError(f"找不到 confirmation：{confirmation_id}")

    def _ensure_project_synced(self) -> None:
        record = self.core.get_project(self.project_id)
        payload = Project.create(project_id=record.project_id, name=record.name, root_path=record.path).to_dict()
        current = self.project_repo.load()
        if not current.id:
            self.project_repo.save(Project.from_dict(payload))
            return
        current.update(name=record.name)
        current.root_path = record.path
        self.project_repo.save(current)

    def _resolve_definition_kind(self, kind: str) -> tuple[str, type]:
        normalized = str(kind or "").strip()
        if normalized not in DEFINITION_KIND_MAP:
            raise KeyError(f"未知的 definition kind：{kind}")
        return DEFINITION_KIND_MAP[normalized]

    def _build_manifest(self) -> AmonManifest:
        project = self.project_repo.load()
        return AmonManifest(
            project=ManifestProject(id=project.id or self.project_id, name=project.name or self.project_id),
            tasks={entity.id: entity for entity in self.definition_repo.list("tasks")},
            agent_profiles={entity.id: entity for entity in self.definition_repo.list("agents")},
            executors={entity.id: entity for entity in self.definition_repo.list("executors")},
            workflows={entity.id: entity for entity in self.definition_repo.list("workflows")},
            templates={entity.id: entity for entity in self.definition_repo.list("templates")},
            tool_policies={entity.id: entity for entity in self.definition_repo.list("tool_policies")},
        )

    def _compile_manifest_workflow(self, workflow_ref: str) -> tuple[AmonManifest, Any]:
        manifest = self._build_manifest()
        bound_workflow = bind_workflow(manifest, workflow_ref)
        manifest.workflows[workflow_ref] = bound_workflow
        return manifest, compile_manifest_workflow(manifest, workflow_ref)

    def _compile_template_run(self, template_ref: str, variables: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
        if template_ref in self.template_library.list_template_ids():
            instantiation = instantiate_builtin_template(template_ref, variables=variables, library=self.template_library)
            graph_payload = dict(instantiation.graph_payload)
            graph_payload.setdefault("version", "taskgraph.v3")
            graph_payload.setdefault("id", f"template.{template_ref}")
            graph_payload.setdefault("name", instantiation.template_name)
            return (
                {
                    "version": "amon.manifest.v1",
                    "project": {"id": self.project_id, "name": self.project_repo.load().name or self.project_id},
                    "templates": {template_ref: {"id": template_ref, "source": "builtin_template"}},
                },
                graph_payload,
            )

        template = self.definition_repo.get("templates", template_ref)
        if not template.workflow_ref:
            raise ValueError("template 缺少 workflow_ref，無法 instantiate")
        manifest, compile_result = self._compile_manifest_workflow(template.workflow_ref)
        return manifest.to_dict(), compile_result.compiled_graph

    def _generate_entity_id(self, kind: str, payload: dict[str, Any]) -> str:
        seed = str(payload.get("name") or payload.get("title") or payload.get("goal") or kind).strip().lower()
        slug = re.sub(r"[^a-z0-9]+", "_", seed).strip("_") or uuid.uuid4().hex[:8]
        prefix = "tool_policy" if kind == "tool-policies" else kind[:-1] if kind.endswith("s") else kind
        return f"{prefix}.{slug}"
