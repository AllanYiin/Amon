"""TaskGraph v3 serialization helpers."""

from __future__ import annotations

import json
from typing import Any

from .payloads import task_spec_to_payload
from .schema import (
    Agent,
    AgentMemoryConfig,
    AgentModelConfig,
    AgentPreview,
    AgentToolRef,
    ArtifactNode,
    BaseNode,
    EdgeCondition,
    EdgeDataMapping,
    GateNode,
    GraphDefinition,
    GraphEdge,
    GraphRun,
    GroupNode,
    NodeError,
    NodeInputBindingV3,
    NodeInputSource,
    NodePort,
    NodeRun,
    OutputPort,
    TaskNode,
    validate_graph_definition,
)

_LEGACY_CONFIG_KEYS = {
    "legacyTaskSpec",
    "legacyExecution",
    "legacyExecutionConfig",
    "legacyPolicy",
    "legacyGuardrails",
    "legacyTaskBoundaries",
    "legacyRoutes",
    "legacyChildren",
    "legacyNodeType",
}


def dumps_graph_definition(graph: GraphDefinition) -> str:
    validate_graph_definition(graph)
    payload = _graph_to_payload(graph)
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _graph_to_payload(graph: GraphDefinition) -> dict[str, Any]:
    graph.sync_relationships()
    return {
        "version": graph.version,
        "id": graph.id,
        "kind": "graph",
        "name": graph.name,
        "description": graph.description,
        "status": graph.status,
        "createdAt": graph.created_at,
        "updatedAt": graph.updated_at,
        "createdBy": graph.created_by,
        "updatedBy": graph.updated_by,
        "entityVersion": graph.entity_version,
        "entryNodeIds": list(graph.entry_node_ids),
        "nodeIds": list(graph.node_ids),
        "edgeIds": list(graph.edge_ids),
        "agentIds": list(graph.agent_ids),
        "canvas": {
            "viewport": {
                "x": graph.canvas.viewport.x,
                "y": graph.canvas.viewport.y,
                "zoom": graph.canvas.viewport.zoom,
            },
            "nodePositions": graph.canvas.node_positions,
            "selectedIds": graph.canvas.selected_ids,
        },
        "settings": {
            "allowCycles": graph.settings.allow_cycles,
            "autoSave": graph.settings.auto_save,
            "runMode": graph.settings.run_mode,
            "concurrencyLimit": graph.settings.concurrency_limit,
            "persistRunHistory": graph.settings.persist_run_history,
        },
        "latestRunId": graph.latest_run_id,
        "lastOpenedAt": graph.last_opened_at,
        "archivedAt": graph.archived_at,
        "tags": graph.tags,
        "metadata": graph.metadata,
        "runtimeCapabilities": {
            "supports_control_edges": graph.runtime_capabilities.supports_control_edges,
            "supports_data_edges": graph.runtime_capabilities.supports_data_edges,
            "supports_parallel_map": graph.runtime_capabilities.supports_parallel_map,
            "supports_recursive": graph.runtime_capabilities.supports_recursive,
            "supports_task_guardrails": graph.runtime_capabilities.supports_task_guardrails,
            "supports_task_boundaries": graph.runtime_capabilities.supports_task_boundaries,
        },
        "nodes": [_node_to_payload(node) for node in graph.nodes],
        "edges": [_edge_to_payload(edge) for edge in graph.edges],
        "agents": [_agent_to_payload(agent) for agent in graph.agents],
        "graphRuns": [_graph_run_to_payload(graph_run) for graph_run in graph.graph_runs],
        "nodeRuns": [_node_run_to_payload(node_run) for node_run in graph.node_runs],
    }


def _node_to_payload(node: BaseNode) -> dict[str, Any]:
    config = {key: value for key, value in dict(node.config).items() if key not in _LEGACY_CONFIG_KEYS}

    payload = {
        "id": node.id,
        "createdAt": node.created_at,
        "updatedAt": node.updated_at,
        "createdBy": node.created_by,
        "updatedBy": node.updated_by,
        "version": node.entity_version,
        "graphId": node.graph_id,
        "type": node.canonical_type,
        "name": node.title,
        "description": node.description,
        "status": node.status,
        "agentId": node.agent_id,
        "promptTemplate": node.prompt_template,
        "config": config,
        "inputPorts": [_node_port_to_payload(port) for port in node.input_ports],
        "outputPorts": [_node_port_to_payload(port) for port in node.output_ports_v3],
        "inputBindings": [_node_input_binding_to_payload(binding) for binding in node.input_bindings_v3],
        "outputs": node.outputs,
        "executionPolicy": {
            "retryable": node.execution_policy.retryable,
            "maxRetries": node.execution_policy.max_retries,
            "timeoutMs": node.execution_policy.timeout_ms,
            "skipIfDisabledInputs": node.execution_policy.skip_if_disabled_inputs,
            "runCondition": {
                "type": node.execution_policy.run_condition.type,
                "expression": node.execution_policy.run_condition.expression,
            },
        },
        "uiState": {
            "collapsed": node.ui_state.collapsed,
            "width": node.ui_state.width,
            "height": node.ui_state.height,
            "color": node.ui_state.color,
            "icon": node.ui_state.icon,
        },
        "upstreamEdgeIds": node.upstream_edge_ids,
        "downstreamEdgeIds": node.downstream_edge_ids,
        "lastRunId": node.last_run_id,
        "lastSucceededAt": node.last_succeeded_at,
        "lastFailedAt": node.last_failed_at,
        "error": _node_error_to_payload(node.error),
        "metadata": node.metadata,
    }
    payload["node_type"] = node.node_type
    payload["title"] = node.title
    if isinstance(node, TaskNode):
        payload["taskSpec"] = task_spec_to_payload(node.task_spec)
        payload["execution"] = node.execution
        if node.execution_config is not None:
            payload["executionConfig"] = node.execution_config
        payload["outputContract"] = {
            "ports": [_legacy_output_port_to_payload(port) for port in node.output_contract.ports]
        }
        payload["policy"] = {
            "rateLimit": node.policy.rate_limit,
            "streamLimit": node.policy.stream_limit,
        }
        if node.guardrails is not None:
            payload["guardrails"] = node.guardrails
        if node.task_boundaries is not None:
            payload["taskBoundaries"] = node.task_boundaries
    elif isinstance(node, GateNode):
        payload["routes"] = [{"onOutcome": route.on_outcome, "toNode": route.to_node} for route in node.routes]
    elif isinstance(node, GroupNode):
        payload["children"] = list(node.children)
    return payload


def _edge_to_payload(edge: GraphEdge) -> dict[str, Any]:
    payload = {
        "id": edge.id,
        "createdAt": edge.created_at,
        "updatedAt": edge.updated_at,
        "createdBy": edge.created_by,
        "updatedBy": edge.updated_by,
        "version": edge.entity_version,
        "graphId": edge.graph_id,
        "type": edge.canonical_type,
        "name": edge.kind or None,
        "label": edge.label or edge.kind or None,
        "status": edge.status,
        "sourceNodeId": edge.from_node,
        "sourcePortKey": edge.source_port_key,
        "targetNodeId": edge.to_node,
        "targetPortKey": edge.target_port_key,
        "condition": _edge_condition_to_payload(edge.condition),
        "mappings": [_edge_mapping_to_payload(mapping) for mapping in edge.mappings],
        "priority": edge.priority,
        "metadata": edge.metadata,
    }
    payload["from"] = edge.from_node
    payload["to"] = edge.to_node
    payload["edge_type"] = edge.edge_type
    payload["kind"] = edge.kind or None
    return payload


def _agent_to_payload(agent: Agent) -> dict[str, Any]:
    return {
        "id": agent.id,
        "kind": "agent",
        "createdAt": agent.created_at,
        "updatedAt": agent.updated_at,
        "createdBy": agent.created_by,
        "updatedBy": agent.updated_by,
        "version": agent.entity_version,
        "name": agent.name,
        "description": agent.description,
        "type": agent.type,
        "status": agent.status,
        "systemPrompt": agent.system_prompt,
        "modelConfig": _agent_model_to_payload(agent.model_config),
        "tools": [_agent_tool_to_payload(tool) for tool in agent.tools],
        "memory": _agent_memory_to_payload(agent.memory),
        "defaultNodeConfig": agent.default_node_config,
        "tags": agent.tags,
        "preview": _agent_preview_to_payload(agent.preview),
        "metadata": agent.metadata,
    }


def _graph_run_to_payload(graph_run: GraphRun) -> dict[str, Any]:
    return {
        "id": graph_run.id,
        "graphId": graph_run.graph_id,
        "status": graph_run.status,
        "trigger": graph_run.trigger,
        "startedAt": graph_run.started_at,
        "endedAt": graph_run.ended_at,
        "nodeRunIds": graph_run.node_run_ids,
        "error": _node_error_to_payload(graph_run.error),
    }


def _node_run_to_payload(node_run: NodeRun) -> dict[str, Any]:
    return {
        "id": node_run.id,
        "graphRunId": node_run.graph_run_id,
        "nodeId": node_run.node_id,
        "status": node_run.status,
        "startedAt": node_run.started_at,
        "endedAt": node_run.ended_at,
        "inputSnapshot": node_run.input_snapshot,
        "outputSnapshot": node_run.output_snapshot,
        "streamBuffer": node_run.stream_buffer,
        "error": _node_error_to_payload(node_run.error),
    }


def _node_port_to_payload(port: NodePort) -> dict[str, Any]:
    return {
        "key": port.key,
        "label": port.label,
        "dataType": port.data_type,
        "required": port.required,
        "multi": port.multi,
    }


def _node_input_binding_to_payload(binding: NodeInputBindingV3) -> dict[str, Any]:
    return {
        "portKey": binding.port_key,
        "source": _node_input_source_to_payload(binding.source),
    }


def _node_input_source_to_payload(source: NodeInputSource) -> dict[str, Any]:
    payload = {"type": source.type}
    if source.value is not None:
        payload["value"] = source.value
    if source.edge_id:
        payload["edgeId"] = source.edge_id
    if source.key:
        payload["key"] = source.key
    if source.node_id:
        payload["nodeId"] = source.node_id
    if source.path:
        payload["path"] = source.path
    return payload


def _edge_condition_to_payload(condition: EdgeCondition) -> dict[str, Any]:
    return {"type": condition.type, "expression": condition.expression}


def _edge_mapping_to_payload(mapping: EdgeDataMapping) -> dict[str, Any]:
    return {
        "sourcePath": mapping.source_path,
        "targetPortKey": mapping.target_port_key,
        "transformExpr": mapping.transform_expr,
        "required": mapping.required,
    }


def _node_error_to_payload(error: NodeError | None) -> dict[str, Any] | None:
    if error is None:
        return None
    return {"code": error.code, "message": error.message, "details": error.details}


def _agent_model_to_payload(model_config: AgentModelConfig | None) -> dict[str, Any] | None:
    if model_config is None:
        return None
    return {
        "provider": model_config.provider,
        "model": model_config.model,
        "temperature": model_config.temperature,
        "maxTokens": model_config.max_tokens,
        "streaming": model_config.streaming,
    }


def _agent_tool_to_payload(tool_ref: AgentToolRef) -> dict[str, Any]:
    return {
        "id": tool_ref.id,
        "name": tool_ref.name,
        "enabled": tool_ref.enabled,
        "config": tool_ref.config,
    }


def _agent_memory_to_payload(memory: AgentMemoryConfig | None) -> dict[str, Any] | None:
    if memory is None:
        return None
    return {
        "enabled": memory.enabled,
        "mode": memory.mode,
        "config": memory.config,
    }


def _agent_preview_to_payload(preview: AgentPreview | None) -> dict[str, Any] | None:
    if preview is None:
        return None
    return {"avatarUrl": preview.avatar_url, "color": preview.color}


def _legacy_output_port_to_payload(port: OutputPort) -> dict[str, Any]:
    return {
        "name": port.name,
        "extractor": port.extractor,
        "parser": port.parser,
        "jsonSchema": port.json_schema,
        "typeRef": port.type_ref,
    }
