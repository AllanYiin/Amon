"""Manifest v1 -> compiled taskgraph.v3 lowering."""

from __future__ import annotations

from typing import Any

from amon.domain import AmonManifest, AgentProfile, ExecutorBinding, TaskDefinition, ToolPolicy, WorkflowDefinition
from amon.domain.compiled_node_metadata import CompiledNodeMetadata
from amon.domain.manifest_validation import ManifestValidationError
from amon.taskgraph3.payloads import (
    AgentTaskConfig,
    ArtifactOutput,
    InputBinding,
    SandboxRunConfig,
    TaskDisplayMetadata,
    TaskSpec,
    ToolCallSpec,
    ToolTaskConfig,
)
from amon.taskgraph3.schema import EdgeCondition, GraphDefinition, GraphEdge, OutputContract, OutputPort, TaskNode

from .compile_result import CompileResult, SnapshotPin


class CompilerError(ValueError):
    def __init__(self, message: str, *, code: str = "AMON_COMPILER_001") -> None:
        super().__init__(message)
        self.code = code


def compile_manifest_workflow(manifest: AmonManifest, workflow_id: str) -> CompileResult:
    workflow = manifest.workflows.get(workflow_id)
    if workflow is None:
        raise CompilerError(f"workflow 不存在：workflow_id={workflow_id}", code="AMON_VALIDATION_002")
    try:
        manifest.validate_compile(workflow_id)
    except ManifestValidationError as exc:
        raise CompilerError(str(exc), code=exc.code) from exc

    task_nodes = [
        _compile_task_node(manifest, workflow, node_id=node.id, task_ref=node.task_ref, executor_ref=node.executor_ref)
        for node in workflow.nodes
    ]
    edges = _compile_edges(workflow)
    snapshot_pins = _build_snapshot_pins(manifest, workflow)
    graph = GraphDefinition(
        id=workflow.id,
        name=workflow.name or workflow.id,
        description=f"compiled from {manifest.version}",
        status="draft",
        created_at=workflow.created_at,
        updated_at=workflow.updated_at,
        nodes=task_nodes,
        edges=edges,
        metadata={
            "source_manifest_version": manifest.version,
            "workflow_ref": workflow.id,
            "snapshotPins": {key: pin.to_dict() for key, pin in snapshot_pins.items()},
        },
    )
    return CompileResult(workflow_ref=workflow.id, graph=graph, snapshot_pins=snapshot_pins)


def _compile_task_node(
    manifest: AmonManifest,
    workflow: WorkflowDefinition,
    *,
    node_id: str,
    task_ref: str,
    executor_ref: str,
) -> TaskNode:
    task = manifest.tasks.get(task_ref)
    executor = manifest.executors.get(executor_ref)
    if task is None:
        raise CompilerError(f"unresolved task_ref：workflow_id={workflow.id}, task_ref={task_ref}", code="AMON_VALIDATION_002")
    if executor is None:
        raise CompilerError(
            f"unresolved executor_ref：workflow_id={workflow.id}, executor_ref={executor_ref}",
            code="AMON_VALIDATION_002",
        )
    task_spec = _compile_task_spec(
        task=task,
        executor=executor,
        agent_profile=manifest.agent_profiles.get(executor.agent_profile_ref or ""),
        tool_policy=manifest.tool_policies.get(executor.tool_policy_ref or ""),
    )
    compiled_metadata = CompiledNodeMetadata.from_compile_inputs(
        task=task,
        executor=executor,
        agent_profile=manifest.agent_profiles.get(executor.agent_profile_ref or ""),
        tool_policy=manifest.tool_policies.get(executor.tool_policy_ref or ""),
    )
    return TaskNode(
        id=node_id,
        title=task.title or task.goal or node_id,
        description=task.goal,
        status="ready",
        created_at=task.created_at,
        updated_at=task.updated_at,
        task_spec=task_spec,
        output_contract=_compile_output_contract(task.output_contract),
        metadata=compiled_metadata.to_dict(),
    )


def _compile_task_spec(
    *,
    task: TaskDefinition,
    executor: ExecutorBinding,
    agent_profile: AgentProfile | None,
    tool_policy: ToolPolicy | None,
) -> TaskSpec:
    if executor.type == "llm":
        instructions = _compose_llm_instructions(task, agent_profile, executor, tool_policy)
        model_policy = agent_profile.model_policy if agent_profile is not None else {}
        return TaskSpec(
            executor="agent",
            agent=AgentTaskConfig(
                system_prompt=agent_profile.system_prompt if agent_profile is not None else None,
                prompt=task.goal,
                instructions=instructions,
                model=str(model_policy.get("model") or model_policy.get("default_model") or "") or None,
                allowed_tools=_allowed_tools_for_llm(executor, tool_policy),
                skills=list(agent_profile.default_skills) if agent_profile is not None else [],
            ),
            input_bindings=_compile_input_bindings(task.input_contract),
            artifacts=_compile_artifacts(task.output_contract),
            display=TaskDisplayMetadata(
                label=task.title or task.id,
                summary=task.goal,
                todo_hint=task.acceptance_criteria[0] if task.acceptance_criteria else None,
                tags=list(task.required_capabilities),
            ),
            runnable=True,
        )
    if executor.type == "tool":
        tools = _compile_tool_calls(executor)
        return TaskSpec(
            executor="tool",
            tool=ToolTaskConfig(tools=tools, skills=[]),
            input_bindings=_compile_input_bindings(task.input_contract),
            artifacts=_compile_artifacts(task.output_contract),
            display=TaskDisplayMetadata(label=task.title or task.id, summary=task.goal, tags=list(task.required_capabilities)),
            runnable=True,
        )
    if executor.type == "sandbox":
        command = str(executor.tool_plan.get("command") or "").strip()
        if not command:
            raise CompilerError(f"sandbox executor 缺少 command：executor_ref={executor.id}")
        return TaskSpec(
            executor="sandbox_run",
            sandbox_run=SandboxRunConfig(
                command=command,
                shell=str(executor.tool_plan.get("shell") or "bash"),
                workdir=str(executor.tool_plan.get("workdir") or ""),
            ),
            input_bindings=_compile_input_bindings(task.input_contract),
            artifacts=_compile_artifacts(task.output_contract),
            display=TaskDisplayMetadata(label=task.title or task.id, summary=task.goal, tags=list(task.required_capabilities)),
            runnable=True,
        )
    raise CompilerError(f"unsupported executor type：executor_ref={executor.id}, type={executor.type}", code="AMON_RUNTIME_001")


def _compile_edges(workflow: WorkflowDefinition) -> list[GraphEdge]:
    edges: list[GraphEdge] = []
    for node in workflow.nodes:
        for dependency in node.depends_on:
            edges.append(
                GraphEdge(
                    id=f"{dependency}->{node.id}",
                    from_node=dependency,
                    to_node=node.id,
                    edge_type="CONTROL",
                    kind="depends_on",
                    status="active",
                    created_at=workflow.created_at,
                    updated_at=workflow.updated_at,
                    condition=EdgeCondition(type="always"),
                )
            )
    return edges


def _build_snapshot_pins(manifest: AmonManifest, workflow: WorkflowDefinition) -> dict[str, SnapshotPin]:
    pins: dict[str, SnapshotPin] = {
        "workflow": SnapshotPin(ref=workflow.id, version=workflow.version, kind="workflow"),
    }
    for node in workflow.nodes:
        task = manifest.tasks[node.task_ref]
        executor = manifest.executors[node.executor_ref]
        pins[f"task:{task.id}"] = SnapshotPin(ref=task.id, version=task.version, kind="task")
        pins[f"executor:{executor.id}"] = SnapshotPin(ref=executor.id, version=executor.version, kind="executor")
        if executor.agent_profile_ref:
            agent = manifest.agent_profiles.get(executor.agent_profile_ref)
            if agent is None:
                raise CompilerError(
                    f"unresolved agent_profile_ref：executor_ref={executor.id}, agent_profile_ref={executor.agent_profile_ref}",
                    code="AMON_VALIDATION_002",
                )
            pins[f"agent:{agent.id}"] = SnapshotPin(ref=agent.id, version=agent.version, kind="agent_profile")
        if executor.tool_policy_ref:
            policy = manifest.tool_policies.get(executor.tool_policy_ref)
            if policy is None:
                raise CompilerError(
                    f"unresolved tool_policy_ref：executor_ref={executor.id}, tool_policy_ref={executor.tool_policy_ref}",
                    code="AMON_VALIDATION_002",
                )
            pins[f"tool_policy:{policy.id}"] = SnapshotPin(ref=policy.id, version=policy.version, kind="tool_policy")
    return pins


def _compose_llm_instructions(
    task: TaskDefinition,
    agent_profile: AgentProfile | None,
    executor: ExecutorBinding,
    tool_policy: ToolPolicy | None,
) -> str:
    sections = [f"目標：{task.goal}"]
    if task.acceptance_criteria:
        sections.append("驗收條件：\n- " + "\n- ".join(task.acceptance_criteria))
    if task.required_capabilities:
        sections.append("需要能力：\n- " + "\n- ".join(task.required_capabilities))
    if agent_profile is not None and agent_profile.purpose:
        sections.append(f"角色目的：{agent_profile.purpose}")
    if executor.tool_invocation_mode:
        sections.append(f"工具模式：{executor.tool_invocation_mode}")
    if tool_policy is not None and tool_policy.allowed_tools:
        sections.append("允許工具：\n- " + "\n- ".join(tool_policy.allowed_tools))
    return "\n\n".join(section for section in sections if section.strip())


def _allowed_tools_for_llm(executor: ExecutorBinding, tool_policy: ToolPolicy | None) -> list[str]:
    if executor.tool_invocation_mode != "delegated" or tool_policy is None:
        return []
    return list(tool_policy.allowed_tools)


def _compile_tool_calls(executor: ExecutorBinding) -> list[ToolCallSpec]:
    tools_raw = executor.tool_plan.get("tools")
    if not isinstance(tools_raw, list) or not tools_raw:
        raise CompilerError(f"tool executor 缺少 tools：executor_ref={executor.id}")
    calls: list[ToolCallSpec] = []
    for item in tools_raw:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or "").strip()
        if not name:
            continue
        calls.append(
            ToolCallSpec(
                name=name,
                args=item.get("args") if isinstance(item.get("args"), dict) else {},
                when_to_use=str(item.get("when_to_use") or item.get("whenToUse") or "").strip() or None,
            )
        )
    if not calls:
        raise CompilerError(f"tool executor 缺少合法 tool 定義：executor_ref={executor.id}")
    return calls


def _compile_output_contract(output_contract: dict[str, Any]) -> OutputContract:
    ports_raw = output_contract.get("ports") if isinstance(output_contract.get("ports"), list) else []
    ports = [
        OutputPort(
            name=str(item.get("name") or "").strip(),
            extractor=str(item.get("extractor") or "").strip() or None,
            parser=str(item.get("parser") or "").strip() or None,
            json_schema=item.get("json_schema") if isinstance(item.get("json_schema"), dict) else (
                item.get("jsonSchema") if isinstance(item.get("jsonSchema"), dict) else None
            ),
            type_ref=str(item.get("type") or item.get("type_ref") or item.get("typeRef") or "").strip() or None,
        )
        for item in ports_raw
        if isinstance(item, dict) and str(item.get("name") or "").strip()
    ]
    return OutputContract(ports=ports)


def _compile_input_bindings(input_contract: dict[str, Any]) -> list[InputBinding]:
    ports_raw = input_contract.get("ports") if isinstance(input_contract.get("ports"), list) else []
    bindings: list[InputBinding] = []
    for item in ports_raw:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or "").strip()
        if not name:
            continue
        default_value = item.get("default")
        source = "literal" if default_value is not None else "variable"
        bindings.append(InputBinding(source=source, key=name, value=default_value))
    return bindings


def _compile_artifacts(output_contract: dict[str, Any]) -> list[ArtifactOutput]:
    ports_raw = output_contract.get("ports") if isinstance(output_contract.get("ports"), list) else []
    return [
        ArtifactOutput(
            name=str(item.get("name") or "").strip(),
            media_type=str(item.get("type") or item.get("media_type") or item.get("mediaType") or "").strip() or None,
            description=str(item.get("description") or "").strip() or None,
            required=bool(item.get("required", False)),
        )
        for item in ports_raw
        if isinstance(item, dict) and str(item.get("name") or "").strip()
    ]
