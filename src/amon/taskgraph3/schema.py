"""TaskGraph v3 schema and graph-level validation."""

from __future__ import annotations

from dataclasses import InitVar, dataclass, field
from typing import Any

from .payloads import TaskSpec, validate_task_spec

_NODE_TYPES = {"TASK", "GATE", "GROUP", "ARTIFACT"}
_EDGE_TYPES = {"CONTROL", "DATA"}
_EXECUTION_TYPES = {"SINGLE", "PARALLEL_MAP", "RECURSIVE"}
_ALLOWED_GATE_OUTCOMES = {"success", "failure", "default", "true", "false"}


@dataclass
class OutputPort:
    name: str
    extractor: str | None = None
    parser: str | None = None
    json_schema: dict[str, Any] | None = None
    type_ref: str | None = None


@dataclass
class OutputContract:
    ports: list[OutputPort] = field(default_factory=list)


@dataclass
class RetryPolicy:
    max_attempts: int = 1
    backoff_s: float = 1.0
    jitter_s: float = 0.0


@dataclass
class BudgetPolicy:
    max_tokens: int | None = None
    max_cost_usd: float | None = None


@dataclass
class TimeoutPolicy:
    hard_s: int = 300
    inactivity_s: int = 60


@dataclass
class Policy:
    rate_limit: int | None = None
    stream_limit: int | None = None
    retry: RetryPolicy = field(default_factory=RetryPolicy)
    budget: BudgetPolicy = field(default_factory=BudgetPolicy)
    timeout: TimeoutPolicy = field(default_factory=TimeoutPolicy)


@dataclass
class RuntimeCapabilities:
    supports_control_edges: bool = True
    supports_data_edges: bool = True
    supports_parallel_map: bool = True
    supports_recursive: bool = True
    supports_task_guardrails: bool = True
    supports_task_boundaries: bool = True


@dataclass
class GateRoute:
    on_outcome: str
    to_node: str


@dataclass
class BaseNode:
    id: str
    node_type: str
    title: str = ""


@dataclass
class TaskNode(BaseNode):
    node_type: str = "TASK"
    description: InitVar[str | None] = None
    execution: str = "SINGLE"
    execution_config: dict[str, Any] | None = None
    task_spec: TaskSpec = field(
        default_factory=lambda: TaskSpec(
            executor="agent",
            runnable=False,
            non_runnable_reason="task_spec 未提供，節點不可直接執行",
        )
    )
    output_contract: OutputContract = field(default_factory=OutputContract)
    policy: Policy = field(default_factory=Policy)
    guardrails: dict[str, Any] | None = None
    task_boundaries: list[str] | None = None


@dataclass
class GateNode(BaseNode):
    node_type: str = "GATE"
    routes: list[GateRoute] = field(default_factory=list)


@dataclass
class GroupNode(BaseNode):
    node_type: str = "GROUP"
    children: list[str] = field(default_factory=list)


@dataclass
class ArtifactNode(BaseNode):
    node_type: str = "ARTIFACT"


@dataclass
class GraphEdge:
    from_node: str
    to_node: str
    edge_type: str
    kind: str


@dataclass
class GraphDefinition:
    version: str = "taskgraph.v3"
    nodes: list[BaseNode] = field(default_factory=list)
    edges: list[GraphEdge] = field(default_factory=list)
    runtime_capabilities: RuntimeCapabilities = field(default_factory=RuntimeCapabilities)


def validate_graph_definition(graph: GraphDefinition) -> None:
    if not isinstance(graph.version, str) or not graph.version.strip():
        raise ValueError("version 必須是非空字串")

    node_ids: set[str] = set()
    gate_nodes: list[GateNode] = []
    group_nodes: list[GroupNode] = []

    for node in graph.nodes:
        _validate_node(node)
        if node.id in node_ids:
            raise ValueError(f"node.id 不可重複：node_id={node.id}")
        node_ids.add(node.id)
        if isinstance(node, GateNode):
            gate_nodes.append(node)
        if isinstance(node, GroupNode):
            group_nodes.append(node)

    for edge in graph.edges:
        if edge.edge_type not in _EDGE_TYPES:
            raise ValueError(f"edge.edge_type 不合法：{edge.edge_type}")
        if not edge.kind or not isinstance(edge.kind, str):
            raise ValueError("edge.kind 必須是非空字串")
        if edge.from_node not in node_ids or edge.to_node not in node_ids:
            raise ValueError(f"edge 指向不存在節點：edge={edge.from_node}->{edge.to_node}")

    for group in group_nodes:
        for child in group.children:
            if child not in node_ids:
                raise ValueError(f"group.children 指向不存在節點：group={group.id}, child={child}")

    for gate in gate_nodes:
        for route in gate.routes:
            if route.on_outcome not in _ALLOWED_GATE_OUTCOMES:
                raise ValueError(
                    f"gate.routes.on_outcome 不合法：node_id={gate.id}, on_outcome={route.on_outcome}"
                )
            if route.to_node not in node_ids:
                raise ValueError(
                    f"gate.routes.to_node 指向不存在節點：node_id={gate.id}, to_node={route.to_node}"
                )


def _validate_node(node: BaseNode) -> None:
    if not isinstance(node.id, str) or not node.id.strip():
        raise ValueError("node.id 必須是非空字串")
    if node.node_type not in _NODE_TYPES:
        raise ValueError(f"node.node_type 不合法：node_id={node.id}, type={node.node_type}")

    if isinstance(node, TaskNode):
        if node.execution not in _EXECUTION_TYPES:
            raise ValueError(f"task.execution 不合法：node_id={node.id}, execution={node.execution}")
        if node.execution_config is not None and not isinstance(node.execution_config, dict):
            raise ValueError(f"task.execution_config 必須是 object：node_id={node.id}")
        if node.execution == "SINGLE" and node.execution_config:
            raise ValueError(f"task.execution_config 僅允許 PARALLEL_MAP/RECURSIVE：node_id={node.id}")
        if node.execution in {"PARALLEL_MAP", "RECURSIVE"} and node.execution_config is None:
            raise ValueError(f"task.execution={node.execution} 時必須提供 execution_config：node_id={node.id}")
        if node.task_spec is None:
            raise ValueError(f"task.task_spec 缺失：node_id={node.id}")
        validate_task_spec(node.id, node.task_spec)
        for port in node.output_contract.ports:
            _validate_output_port(node.id, port)



def _validate_output_port(node_id: str, port: OutputPort) -> None:
    if not isinstance(port.name, str) or not port.name.strip():
        raise ValueError(f"output port name 必須是非空字串：node_id={node_id}")
    if port.extractor is not None and not isinstance(port.extractor, str):
        raise ValueError(f"output port extractor 必須是字串：node_id={node_id}, port={port.name}")
    if port.parser is not None and not isinstance(port.parser, str):
        raise ValueError(f"output port parser 必須是字串：node_id={node_id}, port={port.name}")
    if port.json_schema is not None and not isinstance(port.json_schema, dict):
        raise ValueError(f"output port jsonSchema 必須是 object：node_id={node_id}, port={port.name}")
    if port.type_ref is not None and not isinstance(port.type_ref, str):
        raise ValueError(f"output port typeRef 必須是字串：node_id={node_id}, port={port.name}")
