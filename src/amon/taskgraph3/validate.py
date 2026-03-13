"""Validation helpers for TaskGraph v3 JSON payloads."""

from __future__ import annotations

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


def validate_v3_graph_json(graph_json: dict[str, Any]) -> None:
    graph = graph_definition_from_payload(graph_json)
    validate_graph_definition(graph)


def graph_definition_from_payload(graph_json: dict[str, Any]) -> GraphDefinition:
    raw = _ensure_dict(graph_json, name="v3 graph")
    nodes_payload = raw.get("nodes")
    edges_payload = raw.get("edges")
    if not isinstance(nodes_payload, list) or not isinstance(edges_payload, list):
        raise ValueError("v3 graph 驗證失敗：nodes/edges 必須是 list")

    graph = GraphDefinition(
        version=str(raw.get("version") or raw.get("schemaVersion") or "taskgraph.v3"),
        id=str(raw.get("id") or "graph"),
        name=str(raw.get("name") or "Untitled Graph"),
        description=_optional_str(raw.get("description")),
        status=str(raw.get("status") or "draft"),
        created_at=_optional_str(raw.get("createdAt")) or raw.get("created_at") or raw.get("ts") or "1970-01-01T00:00:00Z",
        updated_at=_optional_str(raw.get("updatedAt")) or raw.get("updated_at") or raw.get("ts") or "1970-01-01T00:00:00Z",
        created_by=_optional_str(raw.get("createdBy")),
        updated_by=_optional_str(raw.get("updatedBy")),
        entity_version=int(raw.get("entityVersion") or raw.get("revision") or 1),
        nodes=[_to_node(item, graph_id=str(raw.get("id") or "graph")) for item in nodes_payload],
        edges=[_to_edge(item, graph_id=str(raw.get("id") or "graph")) for item in edges_payload],
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
        metadata=raw.get("metadata") if isinstance(raw.get("metadata"), dict) else None,
        runtime_capabilities=_to_runtime_capabilities(raw.get("runtimeCapabilities")),
    )
    return graph


def _to_node(raw: Any, *, graph_id: str) -> TaskNode | GateNode | GroupNode | ArtifactNode:
    payload = _ensure_dict(raw, name="v3 node")
    node_type = str(payload.get("node_type") or "").upper().strip()
    canonical_type = str(payload.get("type") or "").strip().lower()
    title = str(payload.get("title") or payload.get("name") or "")
    common_kwargs = {
        "id": str(payload.get("id") or ""),
        "title": title,
        "status": str(payload.get("status") or "dirty"),
        "graph_id": str(payload.get("graphId") or payload.get("graph_id") or graph_id),
        "description": _optional_str(payload.get("description")),
        "agent_id": _optional_str(payload.get("agentId") or payload.get("agent_id")),
        "prompt_template": _optional_str(payload.get("promptTemplate") or payload.get("prompt_template")),
        "config": payload.get("config") if isinstance(payload.get("config"), dict) else {},
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
        "metadata": payload.get("metadata") if isinstance(payload.get("metadata"), dict) else None,
        "created_at": _optional_str(payload.get("createdAt")) or "1970-01-01T00:00:00Z",
        "updated_at": _optional_str(payload.get("updatedAt")) or "1970-01-01T00:00:00Z",
        "created_by": _optional_str(payload.get("createdBy")),
        "updated_by": _optional_str(payload.get("updatedBy")),
        "entity_version": int(payload.get("version") or payload.get("entityVersion") or 1),
    }

    if node_type == "GATE" or canonical_type == "decision":
        routes = _extract_gate_routes(payload)
        return GateNode(routes=routes, **common_kwargs)
    if node_type == "GROUP" or canonical_type == "group":
        children = [str(item) for item in (payload.get("children") or common_kwargs["config"].get("legacyChildren") or [])]
        return GroupNode(children=children, **common_kwargs)
    if node_type == "ARTIFACT" or canonical_type == "output":
        return ArtifactNode(**common_kwargs)

    task_spec = _extract_task_spec(payload, title)
    output_contract = _extract_output_contract(payload)
    execution = str(
        payload.get("execution")
        or common_kwargs["config"].get("legacyExecution")
        or _execution_from_canonical_type(canonical_type, common_kwargs["config"])
    ).upper()
    execution_config = payload.get("executionConfig")
    if execution_config is None:
        legacy_config = common_kwargs["config"].get("legacyExecutionConfig")
        execution_config = legacy_config if isinstance(legacy_config, dict) else None
    policy = _extract_policy(payload)
    return TaskNode(
        execution=execution or "SINGLE",
        execution_config=execution_config if isinstance(execution_config, dict) else None,
        task_spec=task_spec,
        output_contract=output_contract,
        policy=policy,
        guardrails=common_kwargs["config"].get("legacyGuardrails") if isinstance(common_kwargs["config"], dict) else None,
        task_boundaries=common_kwargs["config"].get("legacyTaskBoundaries") if isinstance(common_kwargs["config"], dict) else None,
        **common_kwargs,
    )


def _extract_gate_routes(payload: dict[str, Any]) -> list[GateRoute]:
    routes_raw = payload.get("routes")
    if not isinstance(routes_raw, list):
        config = payload.get("config") if isinstance(payload.get("config"), dict) else {}
        routes_raw = config.get("legacyRoutes") if isinstance(config.get("legacyRoutes"), list) else []
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
    config = payload.get("config") if isinstance(payload.get("config"), dict) else {}
    legacy_task_spec = config.get("legacyTaskSpec")
    if isinstance(legacy_task_spec, dict):
        return task_spec_from_payload(legacy_task_spec)

    input_bindings = [_legacy_input_binding_from_v3(item) for item in _list_of_dicts(payload.get("inputBindings"))]
    prompt_template = _optional_str(payload.get("promptTemplate"))
    agent_id = _optional_str(payload.get("agentId"))
    canonical_type = str(payload.get("type") or "").strip().lower()
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
                    json_schema=port.get("jsonSchema") if isinstance(port.get("jsonSchema"), dict) else None,
                    type_ref=_optional_str(port.get("typeRef")),
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
    config = payload.get("config") if isinstance(payload.get("config"), dict) else {}
    legacy_policy = config.get("legacyPolicy") if isinstance(config.get("legacyPolicy"), dict) else {}
    source = raw_policy or legacy_policy
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
    edge_type = str(payload.get("edge_type") or payload.get("type") or "control")
    mappings = [_to_edge_mapping(item) for item in _list_of_dicts(payload.get("mappings"))]
    condition = _to_edge_condition(payload.get("condition"))
    if condition is None:
        condition = EdgeCondition(type="always")
    return GraphEdge(
        id=str(payload.get("id") or ""),
        from_node=str(payload.get("from") or payload.get("from_node") or payload.get("sourceNodeId") or ""),
        to_node=str(payload.get("to") or payload.get("to_node") or payload.get("targetNodeId") or ""),
        edge_type=str(edge_type),
        kind=str(payload.get("legacyKind") or payload.get("kind") or payload.get("name") or payload.get("label") or ""),
        graph_id=str(payload.get("graphId") or payload.get("graph_id") or graph_id),
        label=_optional_str(payload.get("label")),
        status=str(payload.get("status") or "active"),
        source_port_key=_optional_str(payload.get("sourcePortKey")),
        target_port_key=_optional_str(payload.get("targetPortKey")),
        condition=condition,
        mappings=mappings,
        priority=_to_optional_int(payload.get("priority")),
        metadata=payload.get("metadata") if isinstance(payload.get("metadata"), dict) else None,
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
