"""TaskGraph v3 task payload contract for Amon executors."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

_EXECUTORS = {"agent", "tool", "sandbox_run"}
_BINDING_SOURCES = {"variable", "upstream", "literal"}


@dataclass
class AgentTaskConfig:
    system_prompt: str | None = None
    prompt: str | None = None
    instructions: str | None = None
    model: str | None = None
    allowed_tools: list[str] = field(default_factory=list)
    skills: list[str] = field(default_factory=list)


@dataclass
class ToolCallSpec:
    name: str
    args: dict[str, Any] = field(default_factory=dict)
    when_to_use: str | None = None


@dataclass
class ToolTaskConfig:
    tools: list[ToolCallSpec] = field(default_factory=list)
    skills: list[str] = field(default_factory=list)


@dataclass
class SandboxRunConfig:
    command: str | None = None
    shell: str | None = None
    workdir: str | None = None


@dataclass
class InputBinding:
    source: str
    key: str
    value: Any = None
    from_node: str | None = None
    port: str | None = None


@dataclass
class ArtifactOutput:
    name: str
    media_type: str | None = None
    description: str | None = None
    required: bool = False


@dataclass
class TaskDisplayMetadata:
    label: str | None = None
    summary: str | None = None
    todo_hint: str | None = None
    tags: list[str] = field(default_factory=list)


@dataclass
class TaskSpec:
    executor: str
    agent: AgentTaskConfig | None = None
    tool: ToolTaskConfig | None = None
    sandbox_run: SandboxRunConfig | None = None
    input_bindings: list[InputBinding] = field(default_factory=list)
    artifacts: list[ArtifactOutput] = field(default_factory=list)
    display: TaskDisplayMetadata = field(default_factory=TaskDisplayMetadata)
    runnable: bool = True
    non_runnable_reason: str | None = None


def validate_task_spec(node_id: str, task_spec: TaskSpec) -> None:
    if task_spec.executor not in _EXECUTORS:
        raise ValueError(f"task.task_spec.executor 不合法：node_id={node_id}, executor={task_spec.executor}")

    if not task_spec.runnable:
        if not task_spec.non_runnable_reason:
            raise ValueError(f"task.task_spec 不可執行時需提供 non_runnable_reason：node_id={node_id}")
        return

    if task_spec.executor == "agent":
        if task_spec.agent is None:
            raise ValueError(f"task.task_spec.agent 缺失：node_id={node_id}")
        if not (task_spec.agent.prompt or task_spec.agent.instructions):
            raise ValueError(f"task.task_spec.agent 需至少包含 prompt/instructions：node_id={node_id}")
    elif task_spec.executor == "tool":
        if task_spec.tool is None or not task_spec.tool.tools:
            raise ValueError(f"task.task_spec.tool.tools 不可為空：node_id={node_id}")
    elif task_spec.executor == "sandbox_run":
        if task_spec.sandbox_run is None or not task_spec.sandbox_run.command:
            raise ValueError(f"task.task_spec.sandbox_run.command 不可為空：node_id={node_id}")

    for binding in task_spec.input_bindings:
        if binding.source not in _BINDING_SOURCES:
            raise ValueError(
                f"task.task_spec.input_bindings.source 不合法：node_id={node_id}, source={binding.source}"
            )
        if not binding.key:
            raise ValueError(f"task.task_spec.input_bindings.key 不可為空：node_id={node_id}")
        if binding.source == "upstream" and (not binding.from_node or not binding.port):
            raise ValueError(
                f"task.task_spec.input_bindings upstream 需包含 from_node/port：node_id={node_id}, key={binding.key}"
            )

    for artifact in task_spec.artifacts:
        if not artifact.name:
            raise ValueError(f"task.task_spec.artifacts.name 不可為空：node_id={node_id}")


def task_spec_from_payload(raw: dict[str, Any]) -> TaskSpec:
    tools_payload = raw.get("tool", {}).get("tools", []) if isinstance(raw.get("tool"), dict) else []
    return TaskSpec(
        executor=str(raw.get("executor") or ""),
        agent=_agent_from_payload(raw.get("agent")),
        tool=ToolTaskConfig(
            tools=[
                ToolCallSpec(
                    name=str(item.get("name") or ""),
                    args=item.get("args") if isinstance(item.get("args"), dict) else {},
                    when_to_use=_optional_str(item.get("whenToUse")),
                )
                for item in tools_payload
                if isinstance(item, dict)
            ],
            skills=[str(skill) for skill in (raw.get("tool", {}).get("skills") or [])],
        )
        if isinstance(raw.get("tool"), dict)
        else None,
        sandbox_run=_sandbox_from_payload(raw.get("sandboxRun")),
        input_bindings=[_input_binding_from_payload(item) for item in raw.get("inputBindings", []) if isinstance(item, dict)],
        artifacts=[_artifact_from_payload(item) for item in raw.get("artifacts", []) if isinstance(item, dict)],
        display=_display_from_payload(raw.get("display")),
        runnable=bool(raw.get("runnable", True)),
        non_runnable_reason=_optional_str(raw.get("nonRunnableReason")),
    )


def task_spec_to_payload(task_spec: TaskSpec) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "executor": task_spec.executor,
        "agent": None,
        "tool": None,
        "sandboxRun": None,
        "inputBindings": [
            {
                "source": b.source,
                "key": b.key,
                "value": b.value,
                "fromNode": b.from_node,
                "port": b.port,
            }
            for b in task_spec.input_bindings
        ],
        "artifacts": [
            {
                "name": a.name,
                "mediaType": a.media_type,
                "description": a.description,
                "required": a.required,
            }
            for a in task_spec.artifacts
        ],
        "display": {
            "label": task_spec.display.label,
            "summary": task_spec.display.summary,
            "todoHint": task_spec.display.todo_hint,
            "tags": task_spec.display.tags,
        },
        "runnable": task_spec.runnable,
        "nonRunnableReason": task_spec.non_runnable_reason,
    }
    if task_spec.agent is not None:
        payload["agent"] = {
            "systemPrompt": task_spec.agent.system_prompt,
            "prompt": task_spec.agent.prompt,
            "instructions": task_spec.agent.instructions,
            "model": task_spec.agent.model,
            "allowedTools": task_spec.agent.allowed_tools,
            "skills": task_spec.agent.skills,
        }
    if task_spec.tool is not None:
        payload["tool"] = {
            "tools": [
                {
                    "name": t.name,
                    "args": t.args,
                    "whenToUse": t.when_to_use,
                }
                for t in task_spec.tool.tools
            ],
            "skills": task_spec.tool.skills,
        }
    if task_spec.sandbox_run is not None:
        payload["sandboxRun"] = {
            "command": task_spec.sandbox_run.command,
            "shell": task_spec.sandbox_run.shell,
            "workdir": task_spec.sandbox_run.workdir,
        }
    return payload


def _agent_from_payload(raw: Any) -> AgentTaskConfig | None:
    if not isinstance(raw, dict):
        return None
    return AgentTaskConfig(
        system_prompt=_optional_str(raw.get("systemPrompt")),
        prompt=_optional_str(raw.get("prompt")),
        instructions=_optional_str(raw.get("instructions")),
        model=_optional_str(raw.get("model")),
        allowed_tools=[str(item) for item in (raw.get("allowedTools") or []) if str(item).strip()],
        skills=[str(item) for item in (raw.get("skills") or raw.get("skillNames") or []) if str(item).strip()],
    )


def _sandbox_from_payload(raw: Any) -> SandboxRunConfig | None:
    if not isinstance(raw, dict):
        return None
    return SandboxRunConfig(
        command=_optional_str(raw.get("command")),
        shell=_optional_str(raw.get("shell")),
        workdir=_optional_str(raw.get("workdir")),
    )


def _input_binding_from_payload(raw: dict[str, Any]) -> InputBinding:
    return InputBinding(
        source=str(raw.get("source") or ""),
        key=str(raw.get("key") or ""),
        value=raw.get("value"),
        from_node=_optional_str(raw.get("fromNode")),
        port=_optional_str(raw.get("port")),
    )


def _artifact_from_payload(raw: dict[str, Any]) -> ArtifactOutput:
    return ArtifactOutput(
        name=str(raw.get("name") or ""),
        media_type=_optional_str(raw.get("mediaType")),
        description=_optional_str(raw.get("description")),
        required=bool(raw.get("required", False)),
    )


def _display_from_payload(raw: Any) -> TaskDisplayMetadata:
    if not isinstance(raw, dict):
        return TaskDisplayMetadata()
    return TaskDisplayMetadata(
        label=_optional_str(raw.get("label")),
        summary=_optional_str(raw.get("summary")),
        todo_hint=_optional_str(raw.get("todoHint")),
        tags=[str(tag) for tag in raw.get("tags", [])],
    )


def _optional_str(value: Any) -> str | None:
    if value is None:
        return None
    return str(value)
