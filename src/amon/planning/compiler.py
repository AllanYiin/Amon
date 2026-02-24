"""Compile PlanGraph into GraphRuntime-compatible ExecGraph."""

from __future__ import annotations

from collections import deque
from typing import Any

from .schema import PlanGraph


def compile_plan_to_exec_graph(plan: PlanGraph, *, run_id_var: str = "${run_id}") -> dict[str, Any]:
    nodes: list[dict[str, Any]] = []
    edges: list[dict[str, str]] = []
    terminal_by_task: dict[str, str] = {}

    for task in plan.nodes:
        task_start_nodes: list[str] = []
        prev_id: str | None = None

        for index, tool in enumerate(task.tools):
            tool_id = f"plan_{task.id}_tool_{index + 1}"
            node = {
                "id": tool_id,
                "type": "tool.call",
                "tool": str(tool.get("tool_name") or ""),
                "args": tool.get("args_schema_hint") or {},
                "variables": {
                    "mode": task.llm.get("mode") if isinstance(task.llm, dict) and task.llm.get("mode") else "single",
                    "skill_names": list(task.skills),
                },
            }
            nodes.append(node)
            task_start_nodes.append(tool_id)
            if prev_id:
                edges.append({"from": prev_id, "to": tool_id})
            prev_id = tool_id

        llm_id = None
        if task.requires_llm:
            llm_id = f"plan_{task.id}_llm"
            llm_prompt = _build_llm_prompt(task)
            llm_node = {
                "id": llm_id,
                "type": "agent_task",
                "prompt": llm_prompt,
                "output_path": f"docs/steps/{task.id}.md",
                "variables": {
                    "mode": task.llm.get("mode") if isinstance(task.llm, dict) and task.llm.get("mode") else "plan_execute",
                    "skill_names": list(task.skills),
                },
            }
            nodes.append(llm_node)
            task_start_nodes.append(llm_id)
            if prev_id:
                edges.append({"from": prev_id, "to": llm_id})
            prev_id = llm_id

        if prev_id is None:
            passthrough_id = f"plan_{task.id}_noop"
            nodes.append(
                {
                    "id": passthrough_id,
                    "type": "write_file",
                    "path": f"docs/steps/{task.id}.txt",
                    "content": f"{task.title}\n{task.goal}",
                }
            )
            task_start_nodes.append(passthrough_id)
            prev_id = passthrough_id

        terminal_by_task[task.id] = prev_id

    for task in plan.nodes:
        current_start = _task_start_node(task.id, nodes)
        for dep in task.depends_on:
            dep_terminal = terminal_by_task.get(dep)
            if dep_terminal:
                edges.append({"from": dep_terminal, "to": current_start})

    _ensure_dag(nodes, edges)
    return {
        "nodes": nodes,
        "edges": edges,
        "variables": {
            "run_id": run_id_var,
            "plan_objective": plan.objective,
            "plan_schema_version": plan.schema_version,
        },
    }


def _task_start_node(task_id: str, nodes: list[dict[str, Any]]) -> str:
    prefixes = [f"plan_{task_id}_tool_", f"plan_{task_id}_llm", f"plan_{task_id}_noop"]
    for node in nodes:
        node_id = str(node.get("id") or "")
        if node_id.startswith(prefixes[0]) or node_id == prefixes[1] or node_id == prefixes[2]:
            return node_id
    raise ValueError(f"找不到 task 起始節點：{task_id}")


def _build_llm_prompt(task: Any) -> str:
    llm_payload = task.llm if isinstance(task.llm, dict) else {}
    dod = "\n".join(f"- {item}" for item in task.definition_of_done)
    instructions = str(llm_payload.get("instructions") or "")
    prompt = str(llm_payload.get("prompt") or "")
    return (
        f"任務標題：{task.title}\n"
        f"任務目標：{task.goal}\n"
        f"Definition of Done：\n{dod}\n\n"
        f"Planner Prompt：{prompt}\n"
        f"Planner Instructions：{instructions}"
    )


def _ensure_dag(nodes: list[dict[str, Any]], edges: list[dict[str, str]]) -> None:
    node_ids = [str(node.get("id") or "") for node in nodes]
    indegree = {node_id: 0 for node_id in node_ids}
    adjacency = {node_id: [] for node_id in node_ids}

    for edge in edges:
        source = str(edge.get("from") or "")
        target = str(edge.get("to") or "")
        if source not in indegree or target not in indegree:
            raise ValueError("edge 指向不存在 node")
        adjacency[source].append(target)
        indegree[target] += 1

    queue = deque([node_id for node_id, count in indegree.items() if count == 0])
    visited = 0
    while queue:
        current = queue.popleft()
        visited += 1
        for nxt in adjacency[current]:
            indegree[nxt] -= 1
            if indegree[nxt] == 0:
                queue.append(nxt)

    if visited != len(node_ids):
        raise ValueError("compiler 產生的 ExecGraph 含循環，非 DAG")
