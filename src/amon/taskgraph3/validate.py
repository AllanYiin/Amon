"""Validation helpers for TaskGraph v3 JSON payloads."""

from __future__ import annotations

import json
from typing import Any

from .payloads import (
    AgentTaskConfig,
    ArtifactOutput,
    InputBinding,
    SandboxRunConfig,
    TaskDisplayMetadata,
    TaskSpec,
    ToolCallSpec,
    ToolTaskConfig,
    task_spec_from_payload,
)
from .schema import (
    Agent,
    AgentMemoryConfig,
    AgentModelConfig,
    AgentPreview,
    AgentToolRef,
    ArtifactNode,
    EdgeCondition,
    EdgeDataMapping,
    GateNode,
    GateRoute,
    GraphCanvas,
    GraphDefinition,
    GraphEdge,
    GraphRun,
    GraphSettings,
    GraphViewport,
    GroupNode,
    NodeError,
    NodeExecutionCondition,
    NodeExecutionPolicy,
    NodeInputBindingV3,
    NodeInputSource,
    NodePort,
    NodeRun,
    NodeUIState,
    OutputContract,
    OutputPort,
    RuntimeCapabilities,
    TaskNode,
    validate_graph_definition,
)

_FORBIDDEN_LEGACY_KEYS = {
    "schemaVersion",
    "legacyTaskSpec",
    "legacyExecution",
    "legacyExecutionConfig",
    "legacyPolicy",
    "legacyGuardrails",
    "legacyTaskBoundaries",
    "legacyRoutes",
    "legacyChildren",
    "legacyNodeType",
    "legacyKind",
}


def validate_v3_graph_json(graph_json: dict[str, Any]) -> None:
    graph = graph_definition_from_payload(graph_json)
    validate_graph_definition(graph)


def graph_definition_from_payload(graph_json: dict[str, Any]) -> GraphDefinition:
    raw = _ensure_dict(graph_json, name="v3 graph")
    _reject_legacy_shim_keys(raw)
    nodes_payload = raw.get("nodes")
    edges_payload = raw.get("edges")
    if not isinstance(nodes_payload, list) or not isinstance(edges_payload, list):
        raise ValueError("v3 graph 驗證失敗：nodes/edges 必須是 list")
    graph_id = str(raw.get("id") or raw.get("graphId") or "graph")
    metadata = raw.get("metadata") if isinstance(raw.get("metadata"), dict) else {}
    if isinstance(raw.get("globals"), dict):
        metadata = dict(metadata)
        metadata["globals"] = raw.get("globals")

    graph = GraphDefinition(
        version=str(raw.get("version") or "taskgraph.v3"),
        id=graph_id,
        name=str(raw.get("name") or "Untitled Graph"),
        description=_optional_str(raw.get("description")),
        status=str(raw.get("status") or "draft"),
        created_at=_optional_str(raw.get("createdAt")) or raw.get("created_at") or raw.get("ts") or "1970-01-01T00:00:00Z",
        updated_at=_optional_str(raw.get("updatedAt")) or raw.get("updated_at") or raw.get("ts") or "1970-01-01T00:00:00Z",
        created_by=_optional_str(raw.get("createdBy")),
        updated_by=_optional_str(raw.get("updatedBy")),
        entity_version=int(raw.get("entityVersion") or raw.get("revision") or 1),
        nodes=[_to_node(item, graph_id=graph_id) for item in nodes_payload],
        edges=[_to_edge(item, graph_id=graph_id) for item in edges_payload],
        agents=[_to_agent(item) for item in raw.get("agents", []) if isinstance(item, dict)],
        graph_runs=[_to_graph_run(item) for item in raw.get("graphRuns", []) if isinstance(item, dict)],
        node_runs=[_to_node_run(item) for item in raw.get("nodeRuns", []) if isinstance(item, dict)],
        entry_node_ids=[str(item) for item in (raw.get("entryNodeIds") or [])],
        node_ids=[str(item) for item in (raw.get("nodeIds") or [])],
        edge_ids=[str(item) for item in (raw.get("edgeIds") or [])],
        agent_ids=[str(item) for item in (raw.get("agentIds") or [])],
        canvas=_to_graph_canvas(raw.get("canvas")),
        settings=_to_graph_settings(raw.get("settings")),
        latest_run_id=_optional_str(raw.get("latestRunId")),
        last_opened_at=_optional_str(raw.get("lastOpenedAt")),
        archived_at=_optional_str(raw.get("archivedAt")),
        tags=[str(item) for item in (raw.get("tags") or [])] if isinstance(raw.get("tags"), list) else None,
        metadata=metadata or None,
        runtime_capabilities=_to_runtime_capabilities(raw.get("runtimeCapabilities")),
    )
    _hydrate_gate_routes_from_edges(graph)
    return graph


def _to_node(raw: Any, *, graph_id: str) -> TaskNode | GateNode | GroupNode | ArtifactNode:
    payload = _ensure_dict(raw, name="v3 node")
    node_type = str(payload.get("node_type") or payload.get("type") or "").upper().strip()
    canonical_type = str(payload.get("type") or "").strip().lower()
    title = _node_title_from_payload(payload)
    config = payload.get("config") if isinstance(payload.get("config"), dict) else {}
    if payload.get("objective") is not None:
        config = dict(config)
        config["objective"] = payload.get("objective")
    if payload.get("definitionOfDone") is not None:
        config = dict(config)
        config["definitionOfDone"] = payload.get("definitionOfDone")
    if payload.get("constraints") is not None:
        config = dict(config)
        config["constraints"] = payload.get("constraints")
    if isinstance(payload.get("labels"), dict):
        config = dict(config)
        config["labels"] = payload.get("labels")
    if isinstance(payload.get("policy"), dict):
        config = dict(config)
        config["policy_raw"] = payload.get("policy")
    metadata = payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {}
    if isinstance(payload.get("artifact"), dict):
        metadata = dict(metadata)
        metadata["artifact"] = payload.get("artifact")
    if isinstance(payload.get("ui"), dict):
        metadata = dict(metadata)
        metadata["ui"] = payload.get("ui")
    if isinstance(payload.get("outputs"), dict):
        metadata = dict(metadata)
        metadata["planner_outputs"] = payload.get("outputs")
    if isinstance(payload.get("inputs"), dict):
        metadata = dict(metadata)
        metadata["planner_inputs"] = payload.get("inputs")
    if isinstance(payload.get("skillBindings"), list):
        metadata = dict(metadata)
        metadata["skillBindings"] = payload.get("skillBindings")
    if isinstance(payload.get("outcomes"), list):
        metadata = dict(metadata)
        metadata["outcomes"] = payload.get("outcomes")
    common_kwargs = {
        "id": str(payload.get("id") or ""),
        "title": title,
        "status": str(payload.get("status") or "dirty"),
        "graph_id": str(payload.get("graphId") or payload.get("graph_id") or graph_id),
        "description": _optional_str(payload.get("description")) or _optional_str(payload.get("objective")),
        "agent_id": _optional_str(payload.get("agentId") or payload.get("agent_id")),
        "prompt_template": _optional_str(payload.get("promptTemplate") or payload.get("prompt_template")),
        "config": config,
        "input_ports": [_to_node_port(item) for item in _list_of_dicts(payload.get("inputPorts"))],
        "output_ports_v3": [_to_node_port(item) for item in _list_of_dicts(payload.get("outputPorts"))],
        "input_bindings_v3": [_to_node_input_binding(item) for item in _list_of_dicts(payload.get("inputBindings"))],
        "outputs": payload.get("outputs") if isinstance(payload.get("outputs"), dict) else None,
        "execution_policy": _to_execution_policy(payload.get("executionPolicy")),
        "ui_state": _to_ui_state(payload.get("uiState")),
        "upstream_edge_ids": [str(item) for item in (payload.get("upstreamEdgeIds") or [])],
        "downstream_edge_ids": [str(item) for item in (payload.get("downstreamEdgeIds") or [])],
        "last_run_id": _optional_str(payload.get("lastRunId")),
        "last_succeeded_at": _optional_str(payload.get("lastSucceededAt")),
        "last_failed_at": _optional_str(payload.get("lastFailedAt")),
        "error": _to_node_error(payload.get("error")),
        "metadata": metadata or None,
        "created_at": _optional_str(payload.get("createdAt")) or "1970-01-01T00:00:00Z",
        "updated_at": _optional_str(payload.get("updatedAt")) or "1970-01-01T00:00:00Z",
        "created_by": _optional_str(payload.get("createdBy")),
        "updated_by": _optional_str(payload.get("updatedBy")),
        "entity_version": int(payload.get("version") or payload.get("entityVersion") or 1),
    }

    if node_type == "GATE" or canonical_type in {"decision", "gate"}:
        routes = _extract_gate_routes(payload)
        return GateNode(routes=routes, **common_kwargs)
    if node_type == "GROUP" or canonical_type == "group":
        children = [str(item) for item in (payload.get("children") or [])]
        return GroupNode(children=children, **common_kwargs)
    if node_type == "ARTIFACT" or canonical_type in {"output", "artifact"}:
        return ArtifactNode(**common_kwargs)

    task_spec = _extract_task_spec(payload, title)
    output_contract = _extract_output_contract(payload)
    execution, execution_config = _extract_execution(payload, canonical_type, common_kwargs["config"])
    policy = _extract_policy(payload)
    guardrails = payload.get("guardrails")
    if isinstance(guardrails, list):
        guardrails = {"rules": guardrails}
    elif not isinstance(guardrails, dict):
        guardrails = None
    return TaskNode(
        execution=execution or "SINGLE",
        execution_config=execution_config,
        task_spec=task_spec,
        output_contract=output_contract,
        policy=policy,
        guardrails=guardrails,
        task_boundaries=_extract_task_boundaries(payload.get("taskBoundaries")),
        **common_kwargs,
    )


def _extract_gate_routes(payload: dict[str, Any]) -> list[GateRoute]:
    routes_raw = payload.get("routes")
    if not isinstance(routes_raw, list):
        routes_raw = []
    routes: list[GateRoute] = []
    for item in routes_raw:
        if not isinstance(item, dict):
            continue
        routes.append(GateRoute(on_outcome=str(item.get("onOutcome") or item.get("on_outcome") or ""), to_node=str(item.get("toNode") or item.get("to_node") or "")))
    return routes


def _extract_task_spec(payload: dict[str, Any], title: str) -> TaskSpec:
    task_spec_raw = payload.get("taskSpec")
    if isinstance(task_spec_raw, dict):
        return task_spec_from_payload(task_spec_raw)

    input_bindings = [_legacy_input_binding_from_v3(item) for item in _list_of_dicts(payload.get("inputBindings"))]
    prompt_template = _optional_str(payload.get("promptTemplate"))
    agent_id = _optional_str(payload.get("agentId"))
    canonical_type = str(payload.get("type") or "").strip().lower()
    config = payload.get("config") if isinstance(payload.get("config"), dict) else {}
    skill_bindings = _list_of_dicts(payload.get("skillBindings"))
    if canonical_type == "tool":
        tool_calls = []
        for item in _list_of_dicts(config.get("toolCalls")):
            tool_calls.append(
                ToolCallSpec(
                    name=str(item.get("name") or ""),
                    args=item.get("args") if isinstance(item.get("args"), dict) else {},
                    when_to_use=_optional_str(item.get("whenToUse")),
                )
            )
        return TaskSpec(
            executor="tool",
            tool=ToolTaskConfig(tools=tool_calls or [ToolCallSpec(name="tool.unspecified", args={})]),
            input_bindings=input_bindings,
            display=TaskDisplayMetadata(label=title, summary=_optional_str(payload.get("description"))),
            runnable=True,
        )
    if canonical_type == "delay":
        return TaskSpec(
            executor="sandbox_run",
            sandbox_run=SandboxRunConfig(command=str(config.get("command") or "sleep 1"), shell="bash"),
            input_bindings=input_bindings,
            display=TaskDisplayMetadata(label=title, summary="delay"),
            runnable=True,
        )
    if skill_bindings:
        allowed_tools = _extract_skill_binding_tools(skill_bindings)
        primary_skills = [str(item.get("skillId") or item.get("name") or "") for item in skill_bindings if str(item.get("role") or "PRIMARY").upper() == "PRIMARY"]
        fallback_skills = [str(item.get("skillId") or item.get("name") or "") for item in skill_bindings if str(item.get("role") or "").upper() in {"FALLBACK", "VALIDATOR"}]
        objective = _optional_str(payload.get("objective")) or _optional_str(payload.get("description")) or title
        dod_items = _normalize_text_list(payload.get("definitionOfDone"))
        constraint_items = _normalize_text_list(payload.get("constraints"))
        instructions_parts = []
        if objective:
            instructions_parts.append(f"目標：{objective}")
        if dod_items:
            instructions_parts.append("完成定義：\n- " + "\n- ".join(dod_items))
        if constraint_items:
            instructions_parts.append("限制：\n- " + "\n- ".join(constraint_items))
        if primary_skills:
            instructions_parts.append("主要 skill：\n- " + "\n- ".join(primary_skills))
        if fallback_skills:
            instructions_parts.append("輔助 skill：\n- " + "\n- ".join(fallback_skills))
        artifacts = []
        outputs_raw = payload.get("outputs") if isinstance(payload.get("outputs"), dict) else {}
        for artifact_id in outputs_raw.get("artifacts") or []:
            if str(artifact_id).strip():
                artifacts.append(ArtifactOutput(name=str(artifact_id), required=False))
        summary = objective or _optional_str(payload.get("description"))
        todo_hint = dod_items[0] if dod_items else None
        return TaskSpec(
            executor="agent",
            agent=AgentTaskConfig(
                prompt=objective or f"完成「{title}」",
                instructions="\n\n".join(instructions_parts) or "請完成此子任務。",
                model=_optional_str(config.get("model")),
                allowed_tools=allowed_tools,
                skills=[skill for skill in primary_skills + fallback_skills if skill],
            ),
            input_bindings=input_bindings,
            artifacts=artifacts,
            display=TaskDisplayMetadata(
                label=title,
                summary=summary,
                todo_hint=todo_hint,
                tags=[item for item in primary_skills if item],
            ),
            runnable=True,
        )
    agent_cfg = AgentTaskConfig(prompt=prompt_template, instructions=_optional_str(config.get("instructions")), model=_optional_str(config.get("model")))
    if not agent_cfg.prompt and not agent_cfg.instructions:
        return TaskSpec(
            executor="agent",
            agent=AgentTaskConfig(prompt=None, instructions=None, model=None),
            input_bindings=input_bindings,
            artifacts=[ArtifactOutput(name="result")],
            display=TaskDisplayMetadata(label=title, summary="missing taskSpec", tags=["incomplete"]),
            runnable=False,
            non_runnable_reason="taskSpec 缺失，節點不可直接執行",
        )
    if agent_id:
        agent_cfg.instructions = agent_cfg.instructions or f"agent_id={agent_id}"
    return TaskSpec(
        executor="agent",
        agent=agent_cfg,
        input_bindings=input_bindings,
        display=TaskDisplayMetadata(label=title, summary=_optional_str(payload.get("description"))),
        runnable=True,
    )


def _extract_output_contract(payload: dict[str, Any]) -> OutputContract:
    output_contract = payload.get("outputContract") if isinstance(payload.get("outputContract"), dict) else {}
    ports_payload = output_contract.get("ports") if isinstance(output_contract.get("ports"), list) else []
    if ports_payload:
        return OutputContract(
            ports=[
                OutputPort(
                    name=str(port.get("name") or ""),
                    extractor=_optional_str(port.get("extractor")),
                    parser=_optional_str(port.get("parser")),
                    json_schema=port.get("jsonSchema") if isinstance(port.get("jsonSchema"), dict) else (port.get("schema") if isinstance(port.get("schema"), dict) else None),
                    type_ref=_optional_str(port.get("typeRef") or port.get("type")),
                )
                for port in ports_payload
                if isinstance(port, dict)
            ]
        )
    return OutputContract(
        ports=[
            OutputPort(
                name=str(port.get("key") or ""),
                extractor="json" if str(port.get("dataType") or "") in {"object", "array"} else None,
                parser=None,
                json_schema={"type": str(port.get("dataType") or "any")} if str(port.get("dataType") or "") != "any" else None,
                type_ref=str(port.get("dataType") or "any"),
            )
            for port in _list_of_dicts(payload.get("outputPorts"))
        ]
    )


def _extract_policy(payload: dict[str, Any]):
    raw_policy = payload.get("policy") if isinstance(payload.get("policy"), dict) else {}
    source = raw_policy
    from .schema import Policy, RetryPolicy, BudgetPolicy, TimeoutPolicy

    retry_raw = source.get("retry") if isinstance(source.get("retry"), dict) else {}
    timeout_raw = source.get("timeout") if isinstance(source.get("timeout"), dict) else {}
    budget_raw = source.get("budget") if isinstance(source.get("budget"), dict) else {}
    return Policy(
        rate_limit=_to_optional_int(source.get("rateLimit") or source.get("rate_limit")),
        stream_limit=_to_optional_int(source.get("streamLimit") or source.get("stream_limit")),
        retry=RetryPolicy(
            max_attempts=int(retry_raw.get("maxAttempts") or retry_raw.get("max_attempts") or 1),
            backoff_s=float(retry_raw.get("backoffSeconds") or retry_raw.get("backoff_s") or 1.0),
            jitter_s=float(retry_raw.get("jitterSeconds") or retry_raw.get("jitter_s") or 0.0),
        ),
        budget=BudgetPolicy(
            max_tokens=_to_optional_int(budget_raw.get("maxTokens") or budget_raw.get("max_tokens")),
            max_cost_usd=_to_optional_float(budget_raw.get("maxCostUsd") or budget_raw.get("max_cost_usd")),
        ),
        timeout=TimeoutPolicy(
            hard_s=int(timeout_raw.get("hardSeconds") or timeout_raw.get("hard_s") or 300),
            inactivity_s=int(timeout_raw.get("inactivitySeconds") or timeout_raw.get("inactivity_s") or 60),
        ),
    )


def _to_edge(raw: Any, *, graph_id: str) -> GraphEdge:
    payload = _ensure_dict(raw, name="v3 edge")
    control_raw = payload.get("control") if isinstance(payload.get("control"), dict) else {}
    data_raw = payload.get("data") if isinstance(payload.get("data"), dict) else {}
    edge_type = str(payload.get("edge_type") or payload.get("type") or "control")
    mappings = [_to_edge_mapping(item) for item in _list_of_dicts(payload.get("mappings"))]
    if not mappings:
        mappings = [_to_edge_mapping_from_ref(item) for item in _list_of_dicts(data_raw.get("mapping"))]
    condition = _to_edge_condition(payload.get("condition"))
    if condition is None and control_raw:
        expression = _optional_str(control_raw.get("conditionExpr"))
        condition = EdgeCondition(type="expression" if expression else "always", expression=expression)
    if condition is None:
        condition = EdgeCondition(type="always")
    metadata = payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {}
    if control_raw or payload.get("controlKind"):
        metadata = dict(metadata)
        metadata["control"] = {
            "onStatus": _optional_str(control_raw.get("onStatus")),
            "onOutcome": _optional_str(control_raw.get("onOutcome")),
            "conditionExpr": _optional_str(control_raw.get("conditionExpr")),
        }
    if data_raw or payload.get("dataKind"):
        metadata = dict(metadata)
        metadata["data"] = data_raw
    return GraphEdge(
        id=str(payload.get("id") or ""),
        from_node=str(payload.get("from") or payload.get("from_node") or payload.get("sourceNodeId") or ""),
        to_node=str(payload.get("to") or payload.get("to_node") or payload.get("targetNodeId") or ""),
        edge_type=str(edge_type),
        kind=str(payload.get("kind") or payload.get("controlKind") or payload.get("dataKind") or payload.get("name") or payload.get("label") or ""),
        graph_id=str(payload.get("graphId") or payload.get("graph_id") or graph_id),
        label=_optional_str(payload.get("label")),
        status=str(payload.get("status") or "active"),
        source_port_key=_optional_str(payload.get("sourcePortKey")),
        target_port_key=_optional_str(payload.get("targetPortKey")) or _infer_target_port_key(mappings),
        condition=condition,
        mappings=mappings,
        priority=_to_optional_int(payload.get("priority")),
        metadata=metadata or None,
        created_at=_optional_str(payload.get("createdAt")) or "1970-01-01T00:00:00Z",
        updated_at=_optional_str(payload.get("updatedAt")) or "1970-01-01T00:00:00Z",
        created_by=_optional_str(payload.get("createdBy")),
        updated_by=_optional_str(payload.get("updatedBy")),
        entity_version=int(payload.get("version") or payload.get("entityVersion") or 1),
    )


def _to_agent(raw: dict[str, Any]) -> Agent:
    return Agent(
        id=str(raw.get("id") or ""),
        name=str(raw.get("name") or ""),
        description=_optional_str(raw.get("description")),
        type=str(raw.get("type") or "custom"),
        status=str(raw.get("status") or "draft"),
        system_prompt=_optional_str(raw.get("systemPrompt")),
        model_config=_to_agent_model_config(raw.get("modelConfig")),
        tools=[_to_agent_tool_ref(item) for item in _list_of_dicts(raw.get("tools"))],
        memory=_to_agent_memory_config(raw.get("memory")),
        default_node_config=raw.get("defaultNodeConfig") if isinstance(raw.get("defaultNodeConfig"), dict) else None,
        tags=[str(item) for item in (raw.get("tags") or []) if str(item).strip()],
        preview=_to_agent_preview(raw.get("preview")),
        metadata=raw.get("metadata") if isinstance(raw.get("metadata"), dict) else None,
        created_at=_optional_str(raw.get("createdAt")) or "1970-01-01T00:00:00Z",
        updated_at=_optional_str(raw.get("updatedAt")) or "1970-01-01T00:00:00Z",
        created_by=_optional_str(raw.get("createdBy")),
        updated_by=_optional_str(raw.get("updatedBy")),
        entity_version=int(raw.get("version") or raw.get("entityVersion") or 1),
    )


def _reject_legacy_shim_keys(raw: Any, *, path: str = "$") -> None:
    if isinstance(raw, dict):
        for key, value in raw.items():
            key_str = str(key)
            if key_str in _FORBIDDEN_LEGACY_KEYS:
                raise ValueError(f"v3 graph 驗證失敗：禁止 legacy 欄位 {path}.{key_str}")
            _reject_legacy_shim_keys(value, path=f"{path}.{key_str}")
        return
    if isinstance(raw, list):
        for index, item in enumerate(raw):
            _reject_legacy_shim_keys(item, path=f"{path}[{index}]")


def _to_graph_run(raw: dict[str, Any]) -> GraphRun:
    return GraphRun(
        id=str(raw.get("id") or ""),
        graph_id=str(raw.get("graphId") or ""),
        status=str(raw.get("status") or "created"),
        trigger=str(raw.get("trigger") or "manual"),
        started_at=_optional_str(raw.get("startedAt")),
        ended_at=_optional_str(raw.get("endedAt")),
        node_run_ids=[str(item) for item in (raw.get("nodeRunIds") or [])],
        error=_to_node_error(raw.get("error")),
    )


def _to_node_run(raw: dict[str, Any]) -> NodeRun:
    return NodeRun(
        id=str(raw.get("id") or ""),
        graph_run_id=str(raw.get("graphRunId") or ""),
        node_id=str(raw.get("nodeId") or ""),
        status=str(raw.get("status") or "created"),
        started_at=_optional_str(raw.get("startedAt")),
        ended_at=_optional_str(raw.get("endedAt")),
        input_snapshot=raw.get("inputSnapshot") if isinstance(raw.get("inputSnapshot"), dict) else None,
        output_snapshot=raw.get("outputSnapshot") if isinstance(raw.get("outputSnapshot"), dict) else None,
        stream_buffer=_optional_str(raw.get("streamBuffer")),
        error=_to_node_error(raw.get("error")),
    )


def _to_graph_canvas(raw: Any) -> GraphCanvas:
    if not isinstance(raw, dict):
        return GraphCanvas()
    viewport_raw = raw.get("viewport") if isinstance(raw.get("viewport"), dict) else {}
    return GraphCanvas(
        viewport=GraphViewport(
            x=float(viewport_raw.get("x") or 0.0),
            y=float(viewport_raw.get("y") or 0.0),
            zoom=float(viewport_raw.get("zoom") or 1.0),
        ),
        node_positions=raw.get("nodePositions") if isinstance(raw.get("nodePositions"), dict) else {},
        selected_ids=[str(item) for item in (raw.get("selectedIds") or [])],
    )


def _to_graph_settings(raw: Any) -> GraphSettings:
    if not isinstance(raw, dict):
        return GraphSettings()
    return GraphSettings(
        allow_cycles=bool(raw.get("allowCycles", False)),
        auto_save=bool(raw.get("autoSave", True)),
        run_mode=str(raw.get("runMode") or "manual"),
        concurrency_limit=int(raw.get("concurrencyLimit") or 1),
        persist_run_history=bool(raw.get("persistRunHistory", True)),
    )


def _to_runtime_capabilities(raw: Any) -> RuntimeCapabilities:
    if not isinstance(raw, dict):
        return RuntimeCapabilities()
    return RuntimeCapabilities(
        supports_control_edges=bool(raw.get("supports_control_edges", True)),
        supports_data_edges=bool(raw.get("supports_data_edges", True)),
        supports_parallel_map=bool(raw.get("supports_parallel_map", True)),
        supports_recursive=bool(raw.get("supports_recursive", True)),
        supports_task_guardrails=bool(raw.get("supports_task_guardrails", True)),
        supports_task_boundaries=bool(raw.get("supports_task_boundaries", True)),
    )


def _to_node_port(raw: dict[str, Any]) -> NodePort:
    return NodePort(
        key=str(raw.get("key") or raw.get("name") or ""),
        label=str(raw.get("label") or raw.get("key") or raw.get("name") or ""),
        data_type=str(raw.get("dataType") or raw.get("typeRef") or "any"),
        required=bool(raw.get("required", False)),
        multi=bool(raw.get("multi", False)),
    )


def _to_node_input_binding(raw: dict[str, Any]) -> NodeInputBindingV3:
    source_raw = raw.get("source") if isinstance(raw.get("source"), dict) else {}
    return NodeInputBindingV3(
        port_key=str(raw.get("portKey") or raw.get("key") or ""),
        source=NodeInputSource(
            type=str(source_raw.get("type") or ""),
            value=source_raw.get("value"),
            edge_id=_optional_str(source_raw.get("edgeId")),
            key=_optional_str(source_raw.get("key")),
            node_id=_optional_str(source_raw.get("nodeId")),
            path=_optional_str(source_raw.get("path")),
        ),
    )


def _legacy_input_binding_from_v3(raw: dict[str, Any]) -> InputBinding:
    source_raw = raw.get("source") if isinstance(raw.get("source"), dict) else {}
    source_type = str(source_raw.get("type") or "")
    if source_type == "literal":
        return InputBinding(source="literal", key=str(raw.get("portKey") or ""), value=source_raw.get("value"))
    if source_type == "graphInput":
        return InputBinding(source="variable", key=str(raw.get("portKey") or ""), value=source_raw.get("key"))
    if source_type == "nodeOutput":
        return InputBinding(
            source="upstream",
            key=str(raw.get("portKey") or ""),
            from_node=_optional_str(source_raw.get("nodeId")),
            port=_optional_str(source_raw.get("path")) or "raw",
        )
    return InputBinding(source="variable", key=str(raw.get("portKey") or ""), value=source_raw.get("key"))


def _to_execution_policy(raw: Any) -> NodeExecutionPolicy:
    if not isinstance(raw, dict):
        return NodeExecutionPolicy()
    run_condition_raw = raw.get("runCondition") if isinstance(raw.get("runCondition"), dict) else {}
    return NodeExecutionPolicy(
        retryable=bool(raw.get("retryable", True)),
        max_retries=int(raw.get("maxRetries") or 0),
        timeout_ms=_to_optional_int(raw.get("timeoutMs")),
        skip_if_disabled_inputs=bool(raw["skipIfDisabledInputs"]) if "skipIfDisabledInputs" in raw else None,
        run_condition=NodeExecutionCondition(
            type=str(run_condition_raw.get("type") or "always"),
            expression=_optional_str(run_condition_raw.get("expression")),
        ),
    )


def _to_ui_state(raw: Any) -> NodeUIState:
    if not isinstance(raw, dict):
        return NodeUIState()
    return NodeUIState(
        collapsed=bool(raw.get("collapsed", False)),
        width=_to_optional_float(raw.get("width")),
        height=_to_optional_float(raw.get("height")),
        color=_optional_str(raw.get("color")),
        icon=_optional_str(raw.get("icon")),
    )


def _to_node_error(raw: Any) -> NodeError | None:
    if not isinstance(raw, dict):
        return None
    return NodeError(code=str(raw.get("code") or "UNKNOWN"), message=str(raw.get("message") or ""), details=raw.get("details"))


def _to_edge_condition(raw: Any) -> EdgeCondition | None:
    if not isinstance(raw, dict):
        return None
    return EdgeCondition(type=str(raw.get("type") or "always"), expression=_optional_str(raw.get("expression")))


def _to_edge_mapping(raw: dict[str, Any]) -> EdgeDataMapping:
    return EdgeDataMapping(
        source_path=_optional_str(raw.get("sourcePath")),
        target_port_key=str(raw.get("targetPortKey") or ""),
        transform_expr=_optional_str(raw.get("transformExpr")),
        required=bool(raw["required"]) if "required" in raw else None,
    )


def _to_agent_model_config(raw: Any) -> AgentModelConfig | None:
    if not isinstance(raw, dict):
        return None
    return AgentModelConfig(
        provider=str(raw.get("provider") or ""),
        model=str(raw.get("model") or ""),
        temperature=_to_optional_float(raw.get("temperature")),
        max_tokens=_to_optional_int(raw.get("maxTokens")),
        streaming=bool(raw.get("streaming", True)),
    )


def _to_agent_tool_ref(raw: dict[str, Any]) -> AgentToolRef:
    return AgentToolRef(
        id=str(raw.get("id") or ""),
        name=str(raw.get("name") or ""),
        enabled=bool(raw.get("enabled", True)),
        config=raw.get("config") if isinstance(raw.get("config"), dict) else None,
    )


def _to_agent_memory_config(raw: Any) -> AgentMemoryConfig | None:
    if not isinstance(raw, dict):
        return None
    return AgentMemoryConfig(
        enabled=bool(raw.get("enabled", False)),
        mode=str(raw.get("mode") or "none"),
        config=raw.get("config") if isinstance(raw.get("config"), dict) else None,
    )


def _to_agent_preview(raw: Any) -> AgentPreview | None:
    if not isinstance(raw, dict):
        return None
    return AgentPreview(avatar_url=_optional_str(raw.get("avatarUrl")), color=_optional_str(raw.get("color")))


def _execution_from_canonical_type(canonical_type: str, config: dict[str, Any]) -> str:
    execution = str(config.get("executionMode") or "").strip().upper()
    if execution:
        return execution
    return "SINGLE"


def _node_title_from_payload(payload: dict[str, Any]) -> str:
    return str(payload.get("title") or payload.get("name") or payload.get("objective") or payload.get("id") or "")


def _extract_execution(payload: dict[str, Any], canonical_type: str, config: dict[str, Any]) -> tuple[str, dict[str, Any] | None]:
    execution_raw = payload.get("execution")
    if isinstance(execution_raw, dict):
        mode = str(execution_raw.get("mode") or "SINGLE").upper()
        if mode == "PARALLEL_MAP" and isinstance(execution_raw.get("parallel"), dict):
            return mode, execution_raw.get("parallel")
        if mode == "RECURSIVE" and isinstance(execution_raw.get("recursive"), dict):
            return mode, execution_raw.get("recursive")
        return mode, None
    mode = str(payload.get("execution") or _execution_from_canonical_type(canonical_type, config)).upper()
    execution_config = payload.get("executionConfig") if isinstance(payload.get("executionConfig"), dict) else None
    return mode, execution_config


def _extract_task_boundaries(raw: Any) -> list[str] | None:
    if not isinstance(raw, list):
        return None
    boundaries: list[str] = []
    for item in raw:
        if isinstance(item, str):
            if item.strip():
                boundaries.append(item)
            continue
        if isinstance(item, dict):
            boundaries.append(json.dumps(item, ensure_ascii=False, sort_keys=True))
    return boundaries or None


def _normalize_text_list(raw: Any) -> list[str]:
    if isinstance(raw, list):
        return [str(item).strip() for item in raw if str(item).strip()]
    if isinstance(raw, str) and raw.strip():
        return [raw.strip()]
    return []


def _extract_skill_binding_tools(skill_bindings: list[dict[str, Any]]) -> list[str]:
    tools: list[str] = []
    for binding in skill_bindings:
        config = binding.get("config") if isinstance(binding.get("config"), dict) else {}
        for tool in config.get("tools") or []:
            tool_name = str(tool).strip()
            if tool_name and tool_name not in tools:
                tools.append(tool_name)
    return tools


def _to_edge_mapping_from_ref(raw: dict[str, Any]) -> EdgeDataMapping:
    from_ref = _optional_str(raw.get("fromRef"))
    to_ref = _optional_str(raw.get("toRef")) or "port:input"
    target_port_key = _ref_to_target_port_key(to_ref)
    return EdgeDataMapping(source_path=from_ref, target_port_key=target_port_key, transform_expr=None, required=None)


def _ref_to_target_port_key(ref: str) -> str:
    if ref.startswith("port:"):
        return ref.split(":", 1)[1] or "input"
    if ref.startswith("var:"):
        return ref.split(":", 1)[1] or "input"
    if ref.startswith("artifact:"):
        return ref.split(":", 1)[1] or "input"
    return ref or "input"


def _infer_target_port_key(mappings: list[EdgeDataMapping]) -> str | None:
    if not mappings:
        return None
    return mappings[0].target_port_key or None


def _hydrate_gate_routes_from_edges(graph: GraphDefinition) -> None:
    gates = {node.id: node for node in graph.nodes if isinstance(node, GateNode)}
    if not gates:
        return
    for edge in graph.edges:
        gate = gates.get(edge.from_node)
        if gate is None or gate.routes:
            continue
        metadata = edge.metadata if isinstance(edge.metadata, dict) else {}
        control = metadata.get("control") if isinstance(metadata.get("control"), dict) else {}
        on_outcome = _optional_str(control.get("onOutcome"))
        if not on_outcome:
            continue
        gate.routes.append(GateRoute(on_outcome=on_outcome, to_node=edge.to_node))


def _to_optional_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    return int(value)


def _to_optional_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    return float(value)


def _optional_str(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value)
    return text if text != "" else None


def _ensure_dict(value: Any, *, name: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{name} 必須是 object")
    return value


def _list_of_dicts(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]
