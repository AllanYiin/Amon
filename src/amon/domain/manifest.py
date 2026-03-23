"""Canonical manifest v1 model."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .entities import AgentProfile, ExecutorBinding, TaskDefinition, Template, ToolPolicy, WorkflowDefinition


@dataclass
class ManifestProject:
    id: str
    name: str

    def to_dict(self) -> dict[str, Any]:
        return {"id": self.id, "name": self.name}

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "ManifestProject":
        return cls(id=str(payload.get("id") or ""), name=str(payload.get("name") or ""))


@dataclass
class AmonManifest:
    version: str = "amon.manifest.v1"
    project: ManifestProject = field(default_factory=lambda: ManifestProject(id="", name=""))
    tasks: dict[str, TaskDefinition] = field(default_factory=dict)
    agent_profiles: dict[str, AgentProfile] = field(default_factory=dict)
    executors: dict[str, ExecutorBinding] = field(default_factory=dict)
    workflows: dict[str, WorkflowDefinition] = field(default_factory=dict)
    templates: dict[str, Template] = field(default_factory=dict)
    tool_policies: dict[str, ToolPolicy] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "project": self.project.to_dict(),
            "tasks": {key: value.to_dict() for key, value in self.tasks.items()},
            "agent_profiles": {key: value.to_dict() for key, value in self.agent_profiles.items()},
            "executors": {key: value.to_dict() for key, value in self.executors.items()},
            "workflows": {key: value.to_dict() for key, value in self.workflows.items()},
            "templates": {key: value.to_dict() for key, value in self.templates.items()},
            "tool_policies": {key: value.to_dict() for key, value in self.tool_policies.items()},
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "AmonManifest":
        return cls(
            version=str(payload.get("version") or "amon.manifest.v1"),
            project=ManifestProject.from_dict(payload.get("project") or {}),
            tasks={key: TaskDefinition.from_dict(value) for key, value in (payload.get("tasks") or {}).items()},
            agent_profiles={
                key: AgentProfile.from_dict(value) for key, value in (payload.get("agent_profiles") or {}).items()
            },
            executors={
                key: ExecutorBinding.from_dict(value) for key, value in (payload.get("executors") or {}).items()
            },
            workflows={
                key: WorkflowDefinition.from_dict(value) for key, value in (payload.get("workflows") or {}).items()
            },
            templates={key: Template.from_dict(value) for key, value in (payload.get("templates") or {}).items()},
            tool_policies={
                key: ToolPolicy.from_dict(value) for key, value in (payload.get("tool_policies") or {}).items()
            },
        )

    def with_definitions(
        self,
        *,
        tasks: dict[str, TaskDefinition] | None = None,
        agent_profiles: dict[str, AgentProfile] | None = None,
        executors: dict[str, ExecutorBinding] | None = None,
        workflows: dict[str, WorkflowDefinition] | None = None,
        templates: dict[str, Template] | None = None,
        tool_policies: dict[str, ToolPolicy] | None = None,
    ) -> "AmonManifest":
        if tasks is not None:
            self.tasks = dict(tasks)
        if agent_profiles is not None:
            self.agent_profiles = dict(agent_profiles)
        if executors is not None:
            self.executors = dict(executors)
        if workflows is not None:
            self.workflows = dict(workflows)
        if templates is not None:
            self.templates = dict(templates)
        if tool_policies is not None:
            self.tool_policies = dict(tool_policies)
        return self

    def validate_references(self) -> None:
        task_ids = set(self.tasks.keys())
        executor_ids = set(self.executors.keys())
        unresolved: list[str] = []
        for workflow in self.workflows.values():
            for node in workflow.nodes:
                if node.task_ref not in task_ids:
                    unresolved.append(f"workflow={workflow.id} node={node.id} missing task_ref={node.task_ref}")
                if node.executor_ref not in executor_ids:
                    unresolved.append(f"workflow={workflow.id} node={node.id} missing executor_ref={node.executor_ref}")
        if unresolved:
            raise ValueError("unresolved refs: " + "; ".join(unresolved))
