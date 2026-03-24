"""Validation layers for manifest authoring, binding, and compile."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from .entities import WorkflowDefinition

if TYPE_CHECKING:
    from .manifest import AmonManifest


@dataclass
class ManifestValidationError(ValueError):
    code: str

    def __init__(self, message: str, *, code: str = "AMON_VALIDATION_001") -> None:
        super().__init__(message)
        self.code = code


def validate_manifest_authoring(manifest: AmonManifest, workflow_id: str | None = None) -> None:
    for workflow in _iter_workflows(manifest, workflow_id):
        _validate_workflow_structure(workflow)
        for node in workflow.nodes:
            if node.task_ref not in manifest.tasks:
                raise ManifestValidationError(
                    f"unresolved task_ref：workflow_id={workflow.id}, node_id={node.id}, task_ref={node.task_ref}",
                    code="AMON_VALIDATION_002",
                )
            if node.executor_ref and node.executor_ref not in manifest.executors:
                raise ManifestValidationError(
                    f"unresolved executor_ref：workflow_id={workflow.id}, node_id={node.id}, executor_ref={node.executor_ref}",
                    code="AMON_VALIDATION_002",
                )


def validate_manifest_bound(
    manifest: AmonManifest,
    workflow_id: str | None = None,
    *,
    workflow: WorkflowDefinition | None = None,
) -> None:
    workflows = [workflow] if workflow is not None else list(_iter_workflows(manifest, workflow_id))
    for current_workflow in workflows:
        _validate_workflow_structure(current_workflow)
        for node in current_workflow.nodes:
            if node.task_ref not in manifest.tasks:
                raise ManifestValidationError(
                    f"unresolved task_ref：workflow_id={current_workflow.id}, node_id={node.id}, task_ref={node.task_ref}",
                    code="AMON_VALIDATION_002",
                )
            if not node.executor_ref:
                raise ManifestValidationError(
                    f"unbound executor_ref：workflow_id={current_workflow.id}, node_id={node.id}",
                    code="AMON_VALIDATION_007",
                )
            if node.executor_ref not in manifest.executors:
                raise ManifestValidationError(
                    f"unresolved executor_ref：workflow_id={current_workflow.id}, node_id={node.id}, executor_ref={node.executor_ref}",
                    code="AMON_VALIDATION_002",
                )


def validate_manifest_compile(manifest: AmonManifest, workflow_id: str) -> None:
    validate_manifest_bound(manifest, workflow_id)


def _iter_workflows(manifest: AmonManifest, workflow_id: str | None) -> list[WorkflowDefinition]:
    if workflow_id is None:
        return list(manifest.workflows.values())
    workflow = manifest.workflows.get(workflow_id)
    if workflow is None:
        raise ManifestValidationError(f"workflow 不存在：workflow_id={workflow_id}", code="AMON_VALIDATION_002")
    return [workflow]


def _validate_workflow_structure(workflow: WorkflowDefinition) -> None:
    node_ids = [node.id for node in workflow.nodes]
    duplicates = sorted({node_id for node_id in node_ids if node_ids.count(node_id) > 1})
    if duplicates:
        raise ManifestValidationError(
            f"duplicate node id：workflow_id={workflow.id}, node_ids={duplicates}",
            code="AMON_VALIDATION_003",
        )

    node_map = {node.id: node for node in workflow.nodes}
    for node in workflow.nodes:
        for dependency in node.depends_on:
            if dependency not in node_map:
                raise ManifestValidationError(
                    f"missing depends_on node：workflow_id={workflow.id}, node_id={node.id}, depends_on={dependency}",
                    code="AMON_VALIDATION_004",
                )
            if dependency == node.id:
                raise ManifestValidationError(
                    f"self dependency：workflow_id={workflow.id}, node_id={node.id}",
                    code="AMON_VALIDATION_005",
                )

    visited: set[str] = set()
    visiting: set[str] = set()
    path: list[str] = []

    def visit(node_id: str) -> None:
        if node_id in visiting:
            start = path.index(node_id)
            cycle = path[start:] + [node_id]
            raise ManifestValidationError(
                f"workflow cycle detected：workflow_id={workflow.id}, cycle={' -> '.join(cycle)}",
                code="AMON_VALIDATION_006",
            )
        if node_id in visited:
            return
        visiting.add(node_id)
        path.append(node_id)
        for dependency in node_map[node_id].depends_on:
            visit(dependency)
        path.pop()
        visiting.remove(node_id)
        visited.add(node_id)

    for node_id in node_map:
        visit(node_id)
