"""TaskGraph 2.0 schema and validator."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from typing import Any

_ALLOWED_OUTPUT_TYPES = {"json", "md", "text", "artifact"}
_ALLOWED_EXTRACT_MODES = {"strict", "best_effort"}


@dataclass
class TaskNodeLLM:
    model: str | None = None
    mode: str | None = None
    temperature: float | None = None
    max_tokens: int | None = None
    tool_choice: str | None = None
    enable_tools: bool = False


@dataclass
class TaskNodeTool:
    name: str
    when_to_use: str | None = None
    required: bool = False
    args_schema_hint: dict[str, Any] | None = None


@dataclass
class TaskNodeOutput:
    type: str = "text"
    extract: str = "best_effort"
    schema: dict[str, Any] | None = None


@dataclass
class TaskNodeGuardrails:
    allow_interrupt: bool = True
    require_human_approval: bool = False
    boundaries: list[str] = field(default_factory=list)


@dataclass
class TaskNodeRetry:
    max_attempts: int = 1
    backoff_s: float = 1.0
    jitter_s: float = 0.0


@dataclass
class TaskNodeTimeout:
    inactivity_s: int = 60
    hard_s: int = 300


@dataclass
class TaskNode:
    id: str
    title: str
    kind: str
    description: str
    role: str = ""
    reads: list[str] = field(default_factory=list)
    writes: dict[str, str] = field(default_factory=dict)
    llm: TaskNodeLLM = field(default_factory=TaskNodeLLM)
    tools: list[TaskNodeTool] = field(default_factory=list)
    steps: list[dict[str, Any]] = field(default_factory=list)
    output: TaskNodeOutput = field(default_factory=TaskNodeOutput)
    guardrails: TaskNodeGuardrails = field(default_factory=TaskNodeGuardrails)
    retry: TaskNodeRetry = field(default_factory=TaskNodeRetry)
    timeout: TaskNodeTimeout = field(default_factory=TaskNodeTimeout)


@dataclass
class TaskEdge:
    from_node: str
    to_node: str
    when: str | None = None


@dataclass
class TaskGraph:
    schema_version: str = "2.0"
    objective: str = ""
    session_defaults: dict[str, Any] = field(default_factory=dict)
    nodes: list[TaskNode] = field(default_factory=list)
    edges: list[TaskEdge] = field(default_factory=list)
    metadata: dict[str, Any] | None = None


def validate_task_graph(graph: TaskGraph) -> None:
    if graph.schema_version != "2.0":
        raise ValueError(f"schema_version 必須固定為 2.0，目前為：{graph.schema_version}")
    if not isinstance(graph.objective, str) or not graph.objective.strip():
        raise ValueError("objective 必須是非空字串")
    if not isinstance(graph.session_defaults, dict):
        raise ValueError("session_defaults 必須是 object")
    if not isinstance(graph.nodes, list) or not graph.nodes:
        raise ValueError("nodes 必須是非空 list")
    if not isinstance(graph.edges, list):
        raise ValueError("edges 必須是 list")

    node_ids: set[str] = set()
    for node in graph.nodes:
        _validate_node(node)
        if node.id in node_ids:
            raise ValueError(f"node.id 不可重複：node_id={node.id}")
        node_ids.add(node.id)

    for edge in graph.edges:
        if edge.from_node not in node_ids or edge.to_node not in node_ids:
            raise ValueError(
                f"edge 指向不存在節點：edge={edge.from_node}->{edge.to_node}"
            )

    _ensure_dag(graph.nodes, graph.edges)


def _validate_node(node: TaskNode) -> None:
    if not isinstance(node.id, str) or not node.id.strip():
        raise ValueError("node.id 必須是非空字串")
    if not isinstance(node.title, str) or not node.title.strip():
        raise ValueError(f"node.title 必須是非空字串：node_id={node.id}")
    if not isinstance(node.kind, str) or not node.kind.strip():
        raise ValueError(f"node.kind 必須是非空字串：node_id={node.id}")
    if not isinstance(node.description, str) or not node.description.strip():
        raise ValueError(f"node.description 必須是非空字串：node_id={node.id}")
    if not isinstance(node.role, str):
        raise ValueError(f"node.role 必須是字串：node_id={node.id}")

    if not isinstance(node.reads, list) or any(not isinstance(item, str) for item in node.reads):
        raise ValueError(f"node.reads 必須是 list[str]：node_id={node.id}")
    if not isinstance(node.writes, dict) or any(
        not isinstance(key, str) or not isinstance(value, str) for key, value in node.writes.items()
    ):
        raise ValueError(f"node.writes 必須是 dict[str,str]：node_id={node.id}")
    if not isinstance(node.steps, list):
        raise ValueError(f"node.steps 必須是 list：node_id={node.id}")
    for index, step in enumerate(node.steps):
        if not isinstance(step, dict):
            raise ValueError(f"node.steps[{index}] 必須是 object：node_id={node.id}")
        step_type = str(step.get("type") or "").strip()
        if step_type not in {"tool", "llm"}:
            raise ValueError(f"node.steps[{index}].type 不合法：node_id={node.id}")
        if step_type == "tool":
            tool_name = step.get("tool_name")
            if not isinstance(tool_name, str) or not tool_name.strip():
                raise ValueError(f"node.steps[{index}].tool_name 必須是非空字串：node_id={node.id}")
            args = step.get("args")
            if args is not None and not isinstance(args, dict):
                raise ValueError(f"node.steps[{index}].args 必須是 object：node_id={node.id}")
            store_as = step.get("store_as")
            if store_as is not None and not isinstance(store_as, str):
                raise ValueError(f"node.steps[{index}].store_as 必須是字串：node_id={node.id}")

    if node.output.type not in _ALLOWED_OUTPUT_TYPES:
        raise ValueError(
            f"node.output.type 不合法：node_id={node.id}, type={node.output.type}"
        )
    if node.output.extract not in _ALLOWED_EXTRACT_MODES:
        raise ValueError(
            f"node.output.extract 不合法：node_id={node.id}, extract={node.output.extract}"
        )

    if node.retry.max_attempts <= 0:
        raise ValueError(f"node.retry.max_attempts 必須 > 0：node_id={node.id}")
    if node.retry.backoff_s <= 0:
        raise ValueError(f"node.retry.backoff_s 必須 > 0：node_id={node.id}")
    if node.retry.jitter_s < 0:
        raise ValueError(f"node.retry.jitter_s 必須 >= 0：node_id={node.id}")
    if node.timeout.inactivity_s <= 0:
        raise ValueError(f"node.timeout.inactivity_s 必須 > 0：node_id={node.id}")
    if node.timeout.hard_s <= 0:
        raise ValueError(f"node.timeout.hard_s 必須 > 0：node_id={node.id}")


def _ensure_dag(nodes: list[TaskNode], edges: list[TaskEdge]) -> None:
    node_ids = [node.id for node in nodes]
    indegree = {node_id: 0 for node_id in node_ids}
    adjacency: dict[str, list[str]] = {node_id: [] for node_id in node_ids}

    for edge in edges:
        if edge.from_node not in indegree or edge.to_node not in indegree:
            raise ValueError(f"edge 指向不存在節點：edge={edge.from_node}->{edge.to_node}")
        adjacency[edge.from_node].append(edge.to_node)
        indegree[edge.to_node] += 1

    queue = deque(node_id for node_id, count in indegree.items() if count == 0)
    visited = 0
    while queue:
        current = queue.popleft()
        visited += 1
        for nxt in adjacency[current]:
            indegree[nxt] -= 1
            if indegree[nxt] == 0:
                queue.append(nxt)

    if visited != len(node_ids):
        raise ValueError("TaskGraph 含循環，非 DAG")
