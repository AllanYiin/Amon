"""Stage 2 binder for resolving task capabilities to executor bindings."""

from __future__ import annotations

from dataclasses import replace

from amon.domain import AmonManifest, WorkflowDefinition, WorkflowNode
from amon.domain.manifest_validation import ManifestValidationError

from .capability_registry import CapabilityRegistry


class BindingError(ValueError):
    def __init__(self, message: str, *, code: str = "AMON_BINDER_001") -> None:
        super().__init__(message)
        self.code = code


def bind_workflow(
    manifest: AmonManifest,
    workflow_id: str,
    *,
    capability_registry: CapabilityRegistry | None = None,
) -> WorkflowDefinition:
    workflow = manifest.workflows.get(workflow_id)
    if workflow is None:
        raise BindingError(f"workflow 不存在：workflow_id={workflow_id}", code="AMON_VALIDATION_002")
    try:
        manifest.validate_authoring(workflow_id)
    except ManifestValidationError as exc:
        raise BindingError(str(exc), code=exc.code) from exc

    registry = capability_registry or CapabilityRegistry.from_manifest(manifest)
    bound_nodes: list[WorkflowNode] = []
    for node in workflow.nodes:
        task = manifest.tasks.get(node.task_ref)
        if task is None:
            raise BindingError(
                f"unresolved task_ref：workflow_id={workflow_id}, node_id={node.id}, task_ref={node.task_ref}",
                code="AMON_VALIDATION_002",
            )
        if node.executor_ref:
            executor = manifest.executors.get(node.executor_ref)
            if executor is None:
                raise BindingError(
                    f"unresolved executor_ref：workflow_id={workflow_id}, node_id={node.id}, executor_ref={node.executor_ref}",
                    code="AMON_VALIDATION_002",
                )
            if executor.status != "active":
                raise BindingError(f"executor 未啟用：node_id={node.id}, executor_ref={node.executor_ref}")
            missing = sorted(set(task.required_capabilities) - set(executor.capabilities))
            if missing:
                raise BindingError(
                    f"executor 無法滿足 capability：node_id={node.id}, executor_ref={node.executor_ref}, missing={missing}"
                )
            bound_nodes.append(replace(node, status="valid" if node.status != "disabled" else node.status))
            continue

        executor = registry.resolve_executor(task)
        if executor is None:
            raise BindingError(
                f"no eligible executor for capability：task_ref={task.id}, required_capabilities={task.required_capabilities}"
            )
        bound_nodes.append(
            replace(
                node,
                executor_ref=executor.id,
                status="valid" if node.status != "disabled" else node.status,
            )
        )

    bound_workflow = workflow.clone()
    bound_workflow.update(nodes=bound_nodes, status="valid" if workflow.status != "archived" else workflow.status)
    try:
        manifest.validate_bound(workflow=bound_workflow)
    except ManifestValidationError as exc:
        raise BindingError(str(exc), code=exc.code) from exc
    return bound_workflow
