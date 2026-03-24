"""Workflow mapping lowering helpers for manifest v1 -> taskgraph.v3."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from amon.domain import AmonManifest, WorkflowDefinition
from amon.taskgraph3.payloads import InputBinding
from amon.taskgraph3.schema import EdgeDataMapping, GraphEdge


WORKFLOW_MAPPING_ERROR_CODE = "AMON_WORKFLOW_002"


@dataclass(frozen=True)
class OutputAliasSpec:
    alias: str
    source: str
    port: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "port": self.port,
        }


@dataclass(frozen=True)
class WorkflowOutputBindingSpec:
    key: str
    from_node: str
    port: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "from_node": self.from_node,
            "port": self.port,
        }


@dataclass(frozen=True)
class CompiledWorkflowSemantics:
    input_bindings_by_node: dict[str, list[InputBinding]] = field(default_factory=dict)
    data_edges: list[GraphEdge] = field(default_factory=list)
    node_output_mappings: dict[str, dict[str, OutputAliasSpec]] = field(default_factory=dict)
    output_bindings: dict[str, WorkflowOutputBindingSpec] = field(default_factory=dict)

    def metadata(self) -> dict[str, Any]:
        payload: dict[str, Any] = {}
        if self.node_output_mappings:
            payload["node_output_mappings"] = {
                node_id: {alias: spec.to_dict() for alias, spec in aliases.items()}
                for node_id, aliases in self.node_output_mappings.items()
            }
        if self.output_bindings:
            payload["output_bindings"] = {
                key: spec.to_dict()
                for key, spec in self.output_bindings.items()
            }
        return payload


class WorkflowMappingError(ValueError):
    def __init__(self, message: str, *, code: str = WORKFLOW_MAPPING_ERROR_CODE) -> None:
        super().__init__(message)
        self.code = code


def compile_workflow_semantics(manifest: AmonManifest, workflow: WorkflowDefinition) -> CompiledWorkflowSemantics:
    node_ids = {node.id for node in workflow.nodes}
    output_ports_by_node = {
        node.id: _task_output_port_names(manifest, workflow.id, node.task_ref)
        for node in workflow.nodes
    }
    node_output_mappings: dict[str, dict[str, OutputAliasSpec]] = {}
    for node in workflow.nodes:
        aliases = _compile_output_mapping(
            workflow_id=workflow.id,
            node_id=node.id,
            raw_mapping=node.output_mapping,
            output_ports=output_ports_by_node[node.id],
        )
        if aliases:
            node_output_mappings[node.id] = aliases

    input_bindings_by_node: dict[str, list[InputBinding]] = {}
    data_edges: list[GraphEdge] = []
    for node in workflow.nodes:
        bindings, edges = _compile_input_mapping(
            workflow=workflow,
            node_id=node.id,
            raw_mapping=node.input_mapping,
            node_ids=node_ids,
            output_ports_by_node=output_ports_by_node,
            node_output_mappings=node_output_mappings,
        )
        if bindings:
            input_bindings_by_node[node.id] = bindings
            data_edges.extend(edges)

    output_bindings = _compile_workflow_output_bindings(
        workflow=workflow,
        node_ids=node_ids,
        output_ports_by_node=output_ports_by_node,
        node_output_mappings=node_output_mappings,
    )
    return CompiledWorkflowSemantics(
        input_bindings_by_node=input_bindings_by_node,
        data_edges=data_edges,
        node_output_mappings=node_output_mappings,
        output_bindings=output_bindings,
    )


def _task_output_port_names(manifest: AmonManifest, workflow_id: str, task_ref: str) -> set[str]:
    task = manifest.tasks.get(task_ref)
    if task is None:
        raise WorkflowMappingError(
            f"workflow mapping unresolved task：workflow_id={workflow_id}, task_ref={task_ref}",
            code="AMON_VALIDATION_002",
        )
    ports_raw = task.output_contract.get("ports") if isinstance(task.output_contract.get("ports"), list) else []
    return {str(item.get("name") or "").strip() for item in ports_raw if isinstance(item, dict) and str(item.get("name") or "").strip()}


def _compile_output_mapping(
    *,
    workflow_id: str,
    node_id: str,
    raw_mapping: dict[str, Any],
    output_ports: set[str],
) -> dict[str, OutputAliasSpec]:
    aliases: dict[str, OutputAliasSpec] = {}
    for alias, spec in raw_mapping.items():
        alias_key = str(alias or "").strip()
        if not alias_key:
            raise WorkflowMappingError(
                f"workflow output_mapping alias 不可為空：workflow_id={workflow_id}, node_id={node_id}"
            )
        source_ref = _mapping_ref_value(spec, accepted_keys=("from", "port", "source"))
        source_kind, port = _parse_local_output_ref(
            workflow_id=workflow_id,
            node_id=node_id,
            alias=alias_key,
            source_ref=source_ref,
        )
        if source_kind == "port" and port not in output_ports:
            raise WorkflowMappingError(
                f"workflow output_mapping 指向不存在輸出 port：workflow_id={workflow_id}, node_id={node_id}, alias={alias_key}, port={port}"
            )
        aliases[alias_key] = OutputAliasSpec(alias=alias_key, source=source_kind, port=port)
    return aliases


def _compile_input_mapping(
    *,
    workflow: WorkflowDefinition,
    node_id: str,
    raw_mapping: dict[str, Any],
    node_ids: set[str],
    output_ports_by_node: dict[str, set[str]],
    node_output_mappings: dict[str, dict[str, OutputAliasSpec]],
) -> tuple[list[InputBinding], list[GraphEdge]]:
    bindings: list[InputBinding] = []
    edges: list[GraphEdge] = []
    for target_key, spec in raw_mapping.items():
        key = str(target_key or "").strip()
        if not key:
            raise WorkflowMappingError(
                f"workflow input_mapping key 不可為空：workflow_id={workflow.id}, node_id={node_id}"
            )
        if isinstance(spec, dict) and "value" in spec:
            bindings.append(InputBinding(source="literal", key=key, value=spec.get("value")))
            continue
        if isinstance(spec, dict) and "var" in spec:
            bindings.append(InputBinding(source="variable", key=key, value=str(spec.get("var") or key)))
            continue
        from_node, port = _parse_remote_ref(
            workflow_id=workflow.id,
            node_id=node_id,
            field="input_mapping",
            target=key,
            spec=spec,
        )
        if from_node == node_id:
            raise WorkflowMappingError(
                f"workflow input_mapping 不可引用自己：workflow_id={workflow.id}, node_id={node_id}, key={key}"
            )
        if from_node not in node_ids:
            raise WorkflowMappingError(
                f"workflow input_mapping 指向不存在節點：workflow_id={workflow.id}, node_id={node_id}, key={key}, from_node={from_node}"
            )
        available_ports = set(output_ports_by_node.get(from_node, set()))
        available_ports.update(node_output_mappings.get(from_node, {}).keys())
        if port != "raw" and port not in available_ports:
            raise WorkflowMappingError(
                f"workflow input_mapping 指向不存在輸出：workflow_id={workflow.id}, node_id={node_id}, key={key}, from_node={from_node}, port={port}"
            )
        bindings.append(InputBinding(source="upstream", key=key, from_node=from_node, port=port))
        edges.append(
            GraphEdge(
                id=f"{from_node}->{node_id}:{key}",
                from_node=from_node,
                to_node=node_id,
                edge_type="DATA",
                kind="input_mapping",
                status="active",
                created_at=workflow.created_at,
                updated_at=workflow.updated_at,
                source_port_key=port,
                target_port_key=key,
                mappings=[EdgeDataMapping(source_path=port, target_port_key=key)],
                metadata={"workflow_semantics": {"type": "input_mapping"}},
            )
        )
    return bindings, edges


def _compile_workflow_output_bindings(
    *,
    workflow: WorkflowDefinition,
    node_ids: set[str],
    output_ports_by_node: dict[str, set[str]],
    node_output_mappings: dict[str, dict[str, OutputAliasSpec]],
) -> dict[str, WorkflowOutputBindingSpec]:
    bindings: dict[str, WorkflowOutputBindingSpec] = {}
    for key, spec in workflow.output_bindings.items():
        output_key = str(key or "").strip()
        if not output_key:
            raise WorkflowMappingError(f"workflow output_bindings key 不可為空：workflow_id={workflow.id}")
        from_node, port = _parse_remote_ref(
            workflow_id=workflow.id,
            node_id=workflow.id,
            field="output_bindings",
            target=output_key,
            spec=spec,
        )
        if from_node not in node_ids:
            raise WorkflowMappingError(
                f"workflow output_bindings 指向不存在節點：workflow_id={workflow.id}, key={output_key}, from_node={from_node}"
            )
        available_ports = set(output_ports_by_node.get(from_node, set()))
        available_ports.update(node_output_mappings.get(from_node, {}).keys())
        if port != "raw" and port not in available_ports:
            raise WorkflowMappingError(
                f"workflow output_bindings 指向不存在輸出：workflow_id={workflow.id}, key={output_key}, from_node={from_node}, port={port}"
            )
        bindings[output_key] = WorkflowOutputBindingSpec(key=output_key, from_node=from_node, port=port)
    return bindings


def _parse_remote_ref(
    *,
    workflow_id: str,
    node_id: str,
    field: str,
    target: str,
    spec: Any,
) -> tuple[str, str]:
    if isinstance(spec, dict):
        from_node = str(spec.get("from_node") or "").strip()
        port = str(spec.get("port") or "").strip()
        if from_node and port:
            return from_node, port
    ref = _mapping_ref_value(spec, accepted_keys=("from",))
    if "." not in ref:
        raise WorkflowMappingError(
            f"workflow {field} 需使用 node.port 參照：workflow_id={workflow_id}, node_id={node_id}, target={target}"
        )
    from_node, port = ref.split(".", 1)
    if not from_node or not port:
        raise WorkflowMappingError(
            f"workflow {field} 參照格式錯誤：workflow_id={workflow_id}, node_id={node_id}, target={target}, ref={ref}"
        )
    return from_node, port


def _parse_local_output_ref(
    *,
    workflow_id: str,
    node_id: str,
    alias: str,
    source_ref: str,
) -> tuple[str, str | None]:
    ref = str(source_ref or "").strip()
    if not ref:
        raise WorkflowMappingError(
            f"workflow output_mapping 缺少來源：workflow_id={workflow_id}, node_id={node_id}, alias={alias}"
        )
    if ref == "raw":
        return "raw", None
    if "." in ref:
        source_node, port = ref.split(".", 1)
        if source_node != node_id:
            raise WorkflowMappingError(
                f"workflow output_mapping 只能引用本節點輸出：workflow_id={workflow_id}, node_id={node_id}, alias={alias}, ref={ref}"
            )
        ref = port
    return "port", ref


def _mapping_ref_value(spec: Any, *, accepted_keys: tuple[str, ...]) -> str:
    if isinstance(spec, str):
        return spec.strip()
    if isinstance(spec, dict):
        for key in accepted_keys:
            value = spec.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
    return ""
