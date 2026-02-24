"""PlanGraph render helpers."""

from __future__ import annotations

from .schema import PlanGraph


def render_todo_markdown(plan: PlanGraph) -> str:
    lines: list[str] = [
        f"# TODO Plan: {plan.objective}",
        "",
    ]
    for node in plan.nodes:
        dod_summary = "；".join(node.definition_of_done) if node.definition_of_done else "（未提供 DoD）"
        lines.append(f"- [ ] {node.id} {node.title}")
        lines.append(f"  - Goal: {node.goal}")
        lines.append(f"  - DoD: {dod_summary}")
    return "\n".join(lines) + "\n"
