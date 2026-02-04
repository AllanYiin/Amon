"""Intent router for chat messages."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RouterResult:
    type: str

    def to_dict(self) -> dict[str, str]:
        return {"type": self.type}


def route_intent(message: str, project_id: str | None = None, run_id: str | None = None) -> RouterResult:
    if message is None:
        message = ""

    text = message.strip()
    _ = project_id

    if text.startswith("/"):
        return RouterResult(type="command_plan")

    command_keywords = ["建立專案", "列出專案", "刪除", "還原", "排程", "跑範本"]
    if any(keyword in text for keyword in command_keywords):
        return RouterResult(type="command_plan")

    graph_patch_keywords = ["把這次任務存成範本", "抽成變數", "改圖"]
    if any(keyword in text for keyword in graph_patch_keywords):
        return RouterResult(type="graph_patch_plan")

    run_context_keywords = ["請改成", "限制", "不要", "用繁中", "不要用付費"]
    if run_id and any(keyword in text for keyword in run_context_keywords):
        return RouterResult(type="run_context_update")

    return RouterResult(type="chat_response")
