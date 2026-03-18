"""TaskGraph v3 schema and graph-level validation.

This module keeps the legacy Python object model (`TaskNode`, `GraphEdge`, ...)
for runtime compatibility, while validation/serialization target the v3
canonical schema described in the product spec.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from .payloads import TaskSpec, validate_task_spec

_NODE_TYPES = {"TASK", "GATE", "GROUP", "ARTIFACT"}
_CANONICAL_NODE_TYPES = {"input", "prompt", "llm", "transform", "decision", "output", "tool", "delay", "group"}
_EDGE_TYPES = {"CONTROL", "DATA", "CONDITIONAL", "FALLBACK"}
_CANONICAL_EDGE_TYPES = {"control", "data", "conditional", "fallback"}
_EXECUTION_TYPES = {"SINGLE", "PARALLEL_MAP", "RECURSIVE"}
_GRAPH_STATUSES = {"draft", "ready", "running", "paused", "succeeded", "failed", "archived"}
_NODE_STATUSES = {
    "idle",
    "dirty",
    "validating",
    "ready",
    "queued",
    "running",
    "streaming",
    "succeeded",
    "failed",
    "canceled",
    "disabled",
    "skipped",
}
_EDGE_STATUSES = {"active", "disabled", "invalid"}
_AGENT_TYPES = {"llm", "tool-router", "retrieval", "planner", "custom"}
_AGENT_STATUSES = {"draft", "ready", "disabled", "archived"}
_RUN_STATUSES = {"created", "queued", "running", "streaming", "succeeded", "failed", "canceled"}
_ALLOWED_GATE_OUTCOMES = {"success", "failure", "default", "true", "false"}
_DATA_TYPES = {"string", "number", "boolean", "object", "array", "file", "any"}
_DEFAULT_ISO_TS = "1970-01-01T00:00:00Z"


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _first_non_empty(*values: str | None) -> str:
    for value in values:
        if isinstance(value, str) and value.strip():
            return value
    return ""


def _coerce_data_type(raw: str | None, *, fallback: str = "any") -> str:
    value = str(raw or "").strip().lower()
    return value if value in _DATA_TYPES else fallback


def _canonical_edge_type(edge_type: str) -> str:
    normalized = str(edge_type or "").strip().lower()
    if normalized in _CANONICAL_EDGE_TYPES:
        return normalized
    legacy = {"control": "control", "data": "data", "conditional": "conditional", "fallback": "fallback"}
    return legacy.get(normalized, str(edge_type or "").strip().upper().lower())


def _legacy_edge_type(edge_type: str) -> str:
    normalized = str(edge_type or "").strip().lower()
    return {
        "control": "CONTROL",
        "data": "DATA",
        "conditional": "CONDITIONAL",
        "fallback": "FALLBACK",
    }.get(normalized, str(edge_type or "").strip().upper())


def _canonical_node_type(node: BaseNode) -> str:
    if isinstance(node, GroupNode):
        return "group"
    if isinstance(node, GateNode):
        return "decision"
    if isinstance(node, ArtifactNode):
        return "output"
    if isinstance(node, TaskNode):
        executor = node.task_spec.executor if node.task_spec else ""
        if executor == "tool":
            return "tool"
        if executor == "agent":
            return "llm"
        return "transform"
    fallback = str(node.node_type or "").strip().lower()
    return fallback if fallback in _CANONICAL_NODE_TYPES else "transform"


@dataclass
class BaseEntity:
    id: str = ""
    created_at: str = field(default_factory=_utcnow_iso)
    updated_at: str = field(default_factory=_utcnow_iso)
    created_by: str | None = None
    updated_by: str | None = None
    entity_version: int = 1


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
class GraphViewport:
    x: float = 0.0
    y: float = 0.0
    zoom: float = 1.0


@dataclass
class GraphCanvas:
    viewport: GraphViewport = field(default_factory=GraphViewport)
    node_positions: dict[str, dict[str, float]] = field(default_factory=dict)
    selected_ids: list[str] = field(default_factory=list)
    last_panel_tab: str | None = None
    unsaved_checkpoint: dict[str, Any] | None = None


@dataclass
class GraphSettings:
    allow_cycles: bool = False
    auto_save: bool = True
    run_mode: str = "manual"
    concurrency_limit: int = 1
    persist_run_history: bool = True


@dataclass
class NodePort:
    key: str
    label: str
    data_type: str = "any"
    required: bool = False
    multi: bool = False


@dataclass
class NodeExecutionCondition:
    type: str = "always"
    expression: str | None = None


@dataclass
class NodeExecutionPolicy:
    retryable: bool = True
    max_retries: int = 0
    timeout_ms: int | None = None
    skip_if_disabled_inputs: bool | None = None
    run_condition: NodeExecutionCondition = field(default_factory=NodeExecutionCondition)


@dataclass
class NodeInputSource:
    type: str
    value: Any = None
    edge_id: str | None = None
    key: str | None = None
    node_id: str | None = None
    path: str | None = None


@dataclass
class NodeInputBindingV3:
    port_key: str
    source: NodeInputSource


@dataclass
class NodeUIState:
    collapsed: bool = False
    width: float | None = None
    height: float | None = None
    color: str | None = None
    icon: str | None = None


@dataclass
class NodeError:
    code: str
    message: str
    details: Any = None


@dataclass
class EdgeDataMapping:
    source_path: str | None = None
    target_port_key: str = ""
    transform_expr: str | None = None
    required: bool | None = None


@dataclass
class EdgeCondition:
    type: str = "always"
    expression: str | None = None


@dataclass
class AgentModelConfig:
    provider: str = ""
    model: str = ""
    temperature: float | None = None
    max_tokens: int | None = None
    streaming: bool = True


@dataclass
class AgentToolRef:
    id: str = ""
    name: str = ""
    enabled: bool = True
    config: dict[str, Any] | None = None


@dataclass
class AgentMemoryConfig:
    enabled: bool = False
    mode: str = "none"
    config: dict[str, Any] | None = None


@dataclass
class AgentPreview:
    avatar_url: str | None = None
    color: str | None = None


@dataclass
class Agent(BaseEntity):
    name: str = ""
    description: str | None = None
    type: str = "custom"
    status: str = "draft"
    system_prompt: str | None = None
    model_config: AgentModelConfig | None = None
    tools: list[AgentToolRef] = field(default_factory=list)
    memory: AgentMemoryConfig | None = None
    default_node_config: dict[str, Any] | None = None
    tags: list[str] = field(default_factory=list)
    preview: AgentPreview | None = None
    metadata: dict[str, Any] | None = None


@dataclass
class GateRoute:
    on_outcome: str
    to_node: str


@dataclass
class BaseNode(BaseEntity):
    node_type: str = "TASK"
    title: str = ""
    status: str = "dirty"
    graph_id: str = ""
    description: str | None = None
    agent_id: str | None = None
    prompt_template: str | None = None
    config: dict[str, Any] = field(default_factory=dict)
    input_ports: list[NodePort] = field(default_factory=list)
    output_ports_v3: list[NodePort] = field(default_factory=list)
    input_bindings_v3: list[NodeInputBindingV3] = field(default_factory=list)
    outputs: dict[str, Any] | None = None
    execution_policy: NodeExecutionPolicy = field(default_factory=NodeExecutionPolicy)
    ui_state: NodeUIState = field(default_factory=NodeUIState)
    upstream_edge_ids: list[str] = field(default_factory=list)
    downstream_edge_ids: list[str] = field(default_factory=list)
    last_run_id: str | None = None
    last_succeeded_at: str | None = None
    last_failed_at: str | None = None
    error: NodeError | None = None
    metadata: dict[str, Any] | None = None

    @property
    def name(self) -> str:
        return self.title

    @name.setter
    def name(self, value: str) -> None:
        self.title = value

    @property
    def canonical_type(self) -> str:
        return _canonical_node_type(self)


@dataclass
class TaskNode(BaseNode):
    node_type: str = "TASK"
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

    def __post_init__(self) -> None:
        self.node_type = "TASK"
        if not self.title:
            self.title = self.id
        if not self.prompt_template and self.task_spec and self.task_spec.agent is not None:
            self.prompt_template = _first_non_empty(self.task_spec.agent.prompt, self.task_spec.agent.instructions)
        if not self.input_ports and self.task_spec:
            seen: set[str] = set()
            for binding in self.task_spec.input_bindings:
                if binding.key in seen:
                    continue
                self.input_ports.append(NodePort(key=binding.key, label=binding.key))
                seen.add(binding.key)
        if not self.output_ports_v3 and self.output_contract.ports:
            self.output_ports_v3 = [
                NodePort(
                    key=port.name,
                    label=port.name,
                    data_type=_coerce_data_type(port.type_ref or (port.json_schema or {}).get("type")),
                    required=False,
                    multi=_coerce_data_type(port.type_ref or (port.json_schema or {}).get("type")) == "array",
                )
                for port in self.output_contract.ports
            ]
        if self.execution_policy.max_retries == 0 and self.policy.retry.max_attempts > 1:
            self.execution_policy.max_retries = max(0, self.policy.retry.max_attempts - 1)
        if self.execution_policy.timeout_ms is None and self.policy.timeout.hard_s > 0:
            self.execution_policy.timeout_ms = int(self.policy.timeout.hard_s * 1000)


@dataclass
class GateNode(BaseNode):
    node_type: str = "GATE"
    routes: list[GateRoute] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.node_type = "GATE"
        if not self.title:
            self.title = self.id


@dataclass
class GroupNode(BaseNode):
    node_type: str = "GROUP"
    children: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.node_type = "GROUP"
        if not self.title:
            self.title = self.id


@dataclass
class ArtifactNode(BaseNode):
    node_type: str = "ARTIFACT"

    def __post_init__(self) -> None:
        self.node_type = "ARTIFACT"
        if not self.title:
            self.title = self.id


@dataclass
class GraphEdge(BaseEntity):
    from_node: str = ""
    to_node: str = ""
    edge_type: str = "CONTROL"
    kind: str = ""
    graph_id: str = ""
    label: str | None = None
    status: str = "active"
    source_port_key: str | None = None
    target_port_key: str | None = None
    condition: EdgeCondition = field(default_factory=EdgeCondition)
    mappings: list[EdgeDataMapping] = field(default_factory=list)
    priority: int | None = None
    metadata: dict[str, Any] | None = None

    @property
    def canonical_type(self) -> str:
        return _canonical_edge_type(self.edge_type)


@dataclass
class NodeRun(BaseEntity):
    graph_run_id: str = ""
    node_id: str = ""
    status: str = "created"
    started_at: str | None = None
    ended_at: str | None = None
    input_snapshot: dict[str, Any] | None = None
    output_snapshot: dict[str, Any] | None = None
    stream_buffer: str | None = None
    error: NodeError | None = None


@dataclass
class GraphRun(BaseEntity):
    graph_id: str = ""
    status: str = "created"
    trigger: str = "manual"
    started_at: str | None = None
    ended_at: str | None = None
    node_run_ids: list[str] = field(default_factory=list)
    error: NodeError | None = None


@dataclass
class GraphDefinition(BaseEntity):
    version: str = "taskgraph.v3"
    name: str = "Untitled Graph"
    description: str | None = None
    status: str = "draft"
    nodes: list[BaseNode] = field(default_factory=list)
    edges: list[GraphEdge] = field(default_factory=list)
    agents: list[Agent] = field(default_factory=list)
    graph_runs: list[GraphRun] = field(default_factory=list)
    node_runs: list[NodeRun] = field(default_factory=list)
    entry_node_ids: list[str] = field(default_factory=list)
    node_ids: list[str] = field(default_factory=list)
    edge_ids: list[str] = field(default_factory=list)
    agent_ids: list[str] = field(default_factory=list)
    canvas: GraphCanvas = field(default_factory=GraphCanvas)
    settings: GraphSettings = field(default_factory=GraphSettings)
    latest_run_id: str | None = None
    last_opened_at: str | None = None
    archived_at: str | None = None
    tags: list[str] | None = None
    metadata: dict[str, Any] | None = None
    runtime_capabilities: RuntimeCapabilities = field(default_factory=RuntimeCapabilities)

    def __post_init__(self) -> None:
        if not self.id:
            self.id = "graph"

    def derived_node_ids(self) -> list[str]:
        return [node.id for node in self.nodes]

    def derived_edge_ids(self) -> list[str]:
        return [edge.id or f"{edge.from_node}->{edge.to_node}:{index}" for index, edge in enumerate(self.edges)]

    def derived_agent_ids(self) -> list[str]:
        return [agent.id for agent in self.agents]

    def derived_entry_node_ids(self) -> list[str]:
        incoming: dict[str, int] = {node.id: 0 for node in self.nodes}
        for edge in self.edges:
            if edge.status != "active":
                continue
            incoming[edge.to_node] = incoming.get(edge.to_node, 0) + 1
        return [node_id for node_id, count in incoming.items() if count == 0]

    def sync_relationships(self) -> None:
        edge_ids = self.edge_ids or self.derived_edge_ids()
        edge_id_map: dict[tuple[str, str, int], str] = {}
        for index, edge in enumerate(self.edges):
            if not edge.id:
                edge.id = edge_ids[index] if index < len(edge_ids) else f"{edge.from_node}->{edge.to_node}:{index}"
            if not edge.graph_id:
                edge.graph_id = self.id
            if edge.canonical_type == "data" and not edge.mappings:
                edge.mappings = [EdgeDataMapping(source_path="$", target_port_key=edge.target_port_key or "input")]
            edge_id_map[(edge.from_node, edge.to_node, index)] = edge.id
        incoming: dict[str, list[str]] = defaultdict(list)
        outgoing: dict[str, list[str]] = defaultdict(list)
        for index, edge in enumerate(self.edges):
            edge_id = edge.id or edge_id_map[(edge.from_node, edge.to_node, index)]
            outgoing[edge.from_node].append(edge_id)
            incoming[edge.to_node].append(edge_id)
        for node in self.nodes:
            if not node.graph_id:
                node.graph_id = self.id
            node.upstream_edge_ids = list(incoming.get(node.id, []))
            node.downstream_edge_ids = list(outgoing.get(node.id, []))
        self.node_ids = self.derived_node_ids()
        self.edge_ids = [edge.id for edge in self.edges]
        self.agent_ids = self.derived_agent_ids()
        if not self.entry_node_ids:
            self.entry_node_ids = self.derived_entry_node_ids()
        if not self.latest_run_id and self.graph_runs:
            self.latest_run_id = self.graph_runs[-1].id


def validate_graph_definition(graph: GraphDefinition) -> None:
    if not isinstance(graph.version, str) or not graph.version.strip():
        raise ValueError("version 必須是非空字串")
    if graph.status not in _GRAPH_STATUSES:
        raise ValueError(f"graph.status 不合法：{graph.status}")
    if graph.settings.run_mode not in {"manual", "sequential", "topological"}:
        raise ValueError(f"graph.settings.run_mode 不合法：{graph.settings.run_mode}")
    if graph.settings.concurrency_limit <= 0:
        raise ValueError("graph.settings.concurrency_limit 必須大於 0")
    if graph.entity_version <= 0:
        raise ValueError("graph.entity_version 必須大於 0")

    graph.sync_relationships()

    node_ids: set[str] = set()
    edge_ids: set[str] = set()
    agent_ids: set[str] = set()
    gate_nodes: list[GateNode] = []
    group_nodes: list[GroupNode] = []

    for node in graph.nodes:
        _validate_node(node)
        if node.id in node_ids:
            raise ValueError(f"node.id 不可重複：node_id={node.id}")
        node_ids.add(node.id)
        if node.graph_id and node.graph_id != graph.id:
            raise ValueError(f"node.graph_id 必須與 graph.id 一致：node_id={node.id}")
        if isinstance(node, GateNode):
            gate_nodes.append(node)
        if isinstance(node, GroupNode):
            group_nodes.append(node)

    for agent in graph.agents:
        _validate_agent(agent)
        if agent.id in agent_ids:
            raise ValueError(f"agent.id 不可重複：agent_id={agent.id}")
        agent_ids.add(agent.id)

    for edge in graph.edges:
        _validate_edge(edge)
        if edge.id in edge_ids:
            raise ValueError(f"edge.id 不可重複：edge_id={edge.id}")
        edge_ids.add(edge.id)
        if edge.graph_id and edge.graph_id != graph.id:
            raise ValueError(f"edge.graph_id 必須與 graph.id 一致：edge_id={edge.id}")
        if edge.from_node not in node_ids or edge.to_node not in node_ids:
            raise ValueError(f"edge 指向不存在節點：edge={edge.from_node}->{edge.to_node}")
        if edge.from_node == edge.to_node and not graph.settings.allow_cycles:
            raise ValueError(f"edge 不可 self-loop：edge={edge.from_node}->{edge.to_node}")

    if set(graph.node_ids) != node_ids:
        raise ValueError("graph.node_ids 與 node store 不一致")
    if set(graph.edge_ids) != edge_ids:
        raise ValueError("graph.edge_ids 與 edge store 不一致")
    if graph.agent_ids and set(graph.agent_ids) != agent_ids:
        raise ValueError("graph.agent_ids 與 agent store 不一致")
    if any(node_id not in node_ids for node_id in graph.entry_node_ids):
        raise ValueError("graph.entry_node_ids 必須指向 graph 內部節點")

    for node in graph.nodes:
        if node.agent_id and node.agent_id not in agent_ids:
            raise ValueError(f"node.agent_id 指向不存在 agent：node_id={node.id}, agent_id={node.agent_id}")
        if node.upstream_edge_ids and any(edge_id not in edge_ids for edge_id in node.upstream_edge_ids):
            raise ValueError(f"node.upstream_edge_ids 與 edge store 不一致：node_id={node.id}")
        if node.downstream_edge_ids and any(edge_id not in edge_ids for edge_id in node.downstream_edge_ids):
            raise ValueError(f"node.downstream_edge_ids 與 edge store 不一致：node_id={node.id}")
        input_port_keys = {port.key for port in node.input_ports}
        for binding in node.input_bindings_v3:
            if binding.port_key not in input_port_keys:
                raise ValueError(f"node.input_bindings.portKey 不存在：node_id={node.id}, portKey={binding.port_key}")

    for group in group_nodes:
        for child in group.children:
            if child not in node_ids:
                raise ValueError(f"group.children 指向不存在節點：group={group.id}, child={child}")

    for gate in gate_nodes:
        for route in gate.routes:
            if not isinstance(route.on_outcome, str) or not route.on_outcome.strip():
                raise ValueError(
                    f"gate.routes.on_outcome 不合法：node_id={gate.id}, on_outcome={route.on_outcome}"
                )
            if route.to_node not in node_ids:
                raise ValueError(
                    f"gate.routes.to_node 指向不存在節點：node_id={gate.id}, to_node={route.to_node}"
                )

    if not graph.settings.allow_cycles:
        _ensure_acyclic(graph)

    graph_run_ids = {graph_run.id for graph_run in graph.graph_runs}
    node_run_ids = {node_run.id for node_run in graph.node_runs}
    for graph_run in graph.graph_runs:
        _validate_graph_run(graph.id, graph_run, node_run_ids)
    for node_run in graph.node_runs:
        _validate_node_run(graph_run_ids, node_ids, node_run)


def _validate_node(node: BaseNode) -> None:
    if not isinstance(node.id, str) or not node.id.strip():
        raise ValueError("node.id 必須是非空字串")
    if node.node_type not in _NODE_TYPES:
        raise ValueError(f"node.node_type 不合法：node_id={node.id}, type={node.node_type}")
    if node.status not in _NODE_STATUSES:
        raise ValueError(f"node.status 不合法：node_id={node.id}, status={node.status}")
    if node.canonical_type not in _CANONICAL_NODE_TYPES:
        raise ValueError(f"node.type 不合法：node_id={node.id}, type={node.canonical_type}")
    if not isinstance(node.title, str) or not node.title.strip():
        raise ValueError(f"node.title 必須是非空字串：node_id={node.id}")

    for port in node.input_ports:
        _validate_node_port(node.id, port, "input")
    for port in node.output_ports_v3:
        _validate_node_port(node.id, port, "output")

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


def _validate_node_port(node_id: str, port: NodePort, direction: str) -> None:
    if not isinstance(port.key, str) or not port.key.strip():
        raise ValueError(f"{direction} port key 必須是非空字串：node_id={node_id}")
    if not isinstance(port.label, str) or not port.label.strip():
        raise ValueError(f"{direction} port label 必須是非空字串：node_id={node_id}, port={port.key}")
    if port.data_type not in _DATA_TYPES:
        raise ValueError(f"{direction} port dataType 不合法：node_id={node_id}, port={port.key}, dataType={port.data_type}")


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


def _validate_edge(edge: GraphEdge) -> None:
    if not isinstance(edge.id, str) or not edge.id.strip():
        raise ValueError("edge.id 必須是非空字串")
    if _legacy_edge_type(edge.edge_type) not in _EDGE_TYPES:
        raise ValueError(f"edge.edge_type 不合法：{edge.edge_type}")
    if edge.status not in _EDGE_STATUSES:
        raise ValueError(f"edge.status 不合法：edge_id={edge.id}, status={edge.status}")
    if not edge.from_node or not edge.to_node:
        raise ValueError(f"edge source/target 不可為空：edge_id={edge.id}")
    canonical_type = edge.canonical_type
    if canonical_type not in _CANONICAL_EDGE_TYPES:
        raise ValueError(f"edge.type 不合法：edge_id={edge.id}, type={edge.edge_type}")
    if canonical_type == "conditional" and edge.condition.type == "always" and not edge.condition.expression:
        raise ValueError(f"conditional edge 必須帶 condition：edge_id={edge.id}")
    if canonical_type == "data" and not edge.mappings:
        raise ValueError(f"data edge 應至少包含 1 組 mapping：edge_id={edge.id}")
    for mapping in edge.mappings:
        if not mapping.target_port_key:
            raise ValueError(f"edge.mapping.targetPortKey 不可為空：edge_id={edge.id}")


def _validate_agent(agent: Agent) -> None:
    if not agent.id or not agent.name:
        raise ValueError("agent.id / agent.name 必須是非空字串")
    if agent.type not in _AGENT_TYPES:
        raise ValueError(f"agent.type 不合法：agent_id={agent.id}, type={agent.type}")
    if agent.status not in _AGENT_STATUSES:
        raise ValueError(f"agent.status 不合法：agent_id={agent.id}, status={agent.status}")
    if agent.type == "llm":
        if agent.model_config is None:
            raise ValueError(f"agent.type=llm 時必須提供 model_config：agent_id={agent.id}")
        if not agent.model_config.provider or not agent.model_config.model:
            raise ValueError(f"agent.model_config 需包含 provider/model：agent_id={agent.id}")
        if not agent.model_config.streaming:
            raise ValueError(f"type = llm 時 modelConfig.streaming 必須為 true：agent_id={agent.id}")


def _validate_graph_run(graph_id: str, graph_run: GraphRun, node_run_ids: set[str]) -> None:
    if graph_run.graph_id != graph_id:
        raise ValueError(f"graph_run.graph_id 必須與 graph.id 一致：graph_run_id={graph_run.id}")
    if graph_run.status not in _RUN_STATUSES:
        raise ValueError(f"graph_run.status 不合法：graph_run_id={graph_run.id}, status={graph_run.status}")
    for node_run_id in graph_run.node_run_ids:
        if node_run_id not in node_run_ids:
            raise ValueError(f"graph_run.node_run_ids 指向不存在 node_run：graph_run_id={graph_run.id}, node_run_id={node_run_id}")


def _validate_node_run(graph_run_ids: set[str], node_ids: set[str], node_run: NodeRun) -> None:
    if node_run.graph_run_id not in graph_run_ids:
        raise ValueError(f"node_run.graph_run_id 指向不存在 graph_run：node_run_id={node_run.id}")
    if node_run.node_id not in node_ids:
        raise ValueError(f"node_run.node_id 指向不存在 node：node_run_id={node_run.id}, node_id={node_run.node_id}")
    if node_run.status not in _RUN_STATUSES:
        raise ValueError(f"node_run.status 不合法：node_run_id={node_run.id}, status={node_run.status}")


def _ensure_acyclic(graph: GraphDefinition) -> None:
    adjacency: dict[str, list[str]] = defaultdict(list)
    for edge in graph.edges:
        if edge.status != "active":
            continue
        adjacency[edge.from_node].append(edge.to_node)
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(node_id: str) -> None:
        if node_id in visited:
            return
        if node_id in visiting:
            raise ValueError("CYCLE_DETECTED")
        visiting.add(node_id)
        for next_node in adjacency.get(node_id, []):
            visit(next_node)
        visiting.remove(node_id)
        visited.add(node_id)

    for node_id in graph.derived_node_ids():
        visit(node_id)
