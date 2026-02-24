"""PlanGraph schema models."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class PlanContext:
    assumptions: list[str] = field(default_factory=list)
    constraints: list[str] = field(default_factory=list)
    glossary: dict[str, str] = field(default_factory=dict)


@dataclass
class PlanNode:
    id: str
    title: str
    goal: str
    definition_of_done: list[str] = field(default_factory=list)
    depends_on: list[str] = field(default_factory=list)
    requires_llm: bool = False
    llm: dict[str, Any] | None = None
    tools: list[dict[str, Any]] = field(default_factory=list)
    skills: list[str] = field(default_factory=list)
    expected_artifacts: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class PlanGraph:
    schema_version: str = "1.0"
    objective: str = ""
    nodes: list[PlanNode] = field(default_factory=list)
    edges: list[dict[str, str]] = field(default_factory=list)
    context: PlanContext | None = None


def validate_plan_graph(plan: PlanGraph) -> None:
    if not isinstance(plan.schema_version, str) or not plan.schema_version.strip():
        raise ValueError("schema_version 必須是非空字串")
    if not isinstance(plan.objective, str) or not plan.objective.strip():
        raise ValueError("objective 必須是非空字串")
    if not isinstance(plan.nodes, list) or not plan.nodes:
        raise ValueError("nodes 必須是非空清單")

    node_ids: set[str] = set()
    for node in plan.nodes:
        if not isinstance(node.id, str) or not node.id.strip():
            raise ValueError("node.id 必須是非空字串")
        if node.id in node_ids:
            raise ValueError(f"node.id 不可重複：{node.id}")
        node_ids.add(node.id)
        if not isinstance(node.title, str) or not node.title.strip():
            raise ValueError(f"node.title 不可為空：{node.id}")
        if not isinstance(node.goal, str) or not node.goal.strip():
            raise ValueError(f"node.goal 不可為空：{node.id}")
        if not isinstance(node.definition_of_done, list) or any(not isinstance(item, str) for item in node.definition_of_done):
            raise ValueError(f"node.definition_of_done 格式錯誤：{node.id}")
        if not isinstance(node.depends_on, list) or any(not isinstance(item, str) for item in node.depends_on):
            raise ValueError(f"node.depends_on 格式錯誤：{node.id}")
        if not isinstance(node.requires_llm, bool):
            raise ValueError(f"node.requires_llm 必須是 bool：{node.id}")
        if node.requires_llm:
            if not isinstance(node.llm, dict):
                raise ValueError(f"requires_llm=true 時 node.llm 必填：{node.id}")
            for key in ("mode", "prompt", "instructions"):
                if key not in node.llm:
                    raise ValueError(f"node.llm 缺少 {key}：{node.id}")

    for node in plan.nodes:
        for dep in node.depends_on:
            if dep not in node_ids:
                raise ValueError(f"depends_on 指向不存在節點：{node.id}->{dep}")

    if not isinstance(plan.edges, list):
        raise ValueError("edges 必須是 list")
    for edge in plan.edges:
        if not isinstance(edge, dict):
            raise ValueError("edge 必須是物件")
        from_node = edge.get("from")
        to_node = edge.get("to")
        if from_node not in node_ids or to_node not in node_ids:
            raise ValueError("edge 必須指向存在節點")


def infer_edges_from_depends_on(nodes: list[PlanNode]) -> list[dict[str, str]]:
    edges: list[dict[str, str]] = []
    for node in nodes:
        for dep in node.depends_on:
            edges.append({"from": dep, "to": node.id})
    edges.sort(key=lambda item: (item["from"], item["to"]))
    return edges
