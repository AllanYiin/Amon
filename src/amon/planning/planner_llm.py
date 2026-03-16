"""LLM planner for generating TaskGraph v3 TODO graphs."""

from __future__ import annotations

import json
import logging
from pathlib import Path
import re
from typing import Any, Iterable, Protocol

from amon.config import ConfigLoader
from amon.llm_request_log import append_llm_request, build_llm_request_payload
from amon.models import build_provider

from amon.taskgraph3.payloads import AgentTaskConfig, ArtifactOutput, TaskDisplayMetadata, TaskSpec, task_spec_from_payload
from amon.taskgraph3.schema import ArtifactNode, GateNode, GateRoute, GraphDefinition, GraphEdge, GroupNode, TaskNode, validate_graph_definition
from amon.taskgraph3.validate import graph_definition_from_payload

logger = logging.getLogger(__name__)

_CODE_BLOCK_RE = re.compile(r"```(?P<lang>[^\n`]*)\n(?P<content>.*?)```", re.DOTALL)


class LLMClient(Protocol):
    def generate_stream(self, messages: list[dict[str, str]], model: str | None = None) -> Iterable[str]:
        ...


def generate_plan_with_llm(
    message: str,
    *,
    project_id: str | None = None,
    project_path: Path | None = None,
    llm_client: LLMClient | None = None,
    model: str | None = None,
    available_tools: list[dict[str, Any]] | None = None,
    available_skills: list[dict[str, Any]] | None = None,
    run_id: str | None = None,
    thread_id: str | None = None,
    request_id: str | None = None,
) -> GraphDefinition:
    normalized = " ".join((message or "").split())
    if not normalized:
        return _minimal_plan("未提供任務描述")

    try:
        client = llm_client
        selected_model = model
        if client is None:
            client, selected_model = _build_default_client(project_id=project_id, model=model)

        raw = _request_plan(
            client,
            selected_model,
            message=normalized,
            available_tools=available_tools,
            available_skills=available_skills,
            repair_error=None,
            previous_raw=None,
            project_path=project_path,
            project_id=project_id,
            run_id=run_id,
            thread_id=thread_id,
            request_id=request_id,
        )
        try:
            return _loads_graph_definition_from_response(raw)
        except ValueError as exc:
            repaired = _request_plan(
                client,
                selected_model,
                message=normalized,
                available_tools=available_tools,
                available_skills=available_skills,
                repair_error=str(exc),
                previous_raw=raw,
                project_path=project_path,
                project_id=project_id,
                run_id=run_id,
                thread_id=thread_id,
                request_id=request_id,
            )
            return _loads_graph_definition_from_response(repaired)
    except Exception as exc:  # noqa: BLE001
        logger.warning("LLM planner 失敗，改用最小計畫：%s", exc)
        return _minimal_plan(normalized)


def _request_plan(
    llm_client: LLMClient,
    model: str | None,
    *,
    message: str,
    available_tools: list[dict[str, Any]] | None,
    available_skills: list[dict[str, Any]] | None,
    repair_error: str | None,
    previous_raw: str | None,
    project_path: Path | None,
    project_id: str | None,
    run_id: str | None,
    thread_id: str | None,
    request_id: str | None,
) -> str:
    user_prompt = _planner_user_prompt(
        message=message,
        available_tools=available_tools,
        available_skills=available_skills,
        repair_error=repair_error,
        previous_raw=previous_raw,
    )
    messages = [
        {"role": "system", "content": _planner_system_prompt(is_repair=bool(repair_error))},
        {"role": "user", "content": user_prompt},
    ]
    if project_path is not None:
        try:
            append_llm_request(
                project_path,
                build_llm_request_payload(
                    source="planner_llm",
                    provider="configured_llm_client",
                    model=model,
                    project_id=project_id,
                    run_id=run_id,
                    thread_id=thread_id,
                    node_id="__planner__",
                    request_id=request_id,
                    stage="planner_repair" if repair_error else "planner_generation",
                    messages=messages,
                    prompt_text=messages[-1]["content"],
                    metadata={
                        "repair": bool(repair_error),
                        "available_tools_count": len(available_tools or []),
                        "available_skills_count": len(available_skills or []),
                    },
                ),
            )
        except OSError as exc:
            logger.warning("寫入 planner llm request trace 失敗：%s", exc)
    return _collect_stream(llm_client, messages, model)


def _collect_stream(llm_client: LLMClient, messages: list[dict[str, str]], model: str | None) -> str:
    chunks: list[str] = []
    for token in llm_client.generate_stream(messages, model=model):
        chunks.append(token)
    return "".join(chunks).strip()


def _build_default_client(project_id: str | None, model: str | None) -> tuple[LLMClient, str | None]:
    config = ConfigLoader().resolve(project_id=project_id).effective
    provider_name = config.get("amon", {}).get("provider", "openai")
    provider_cfg = config.get("providers", {}).get(provider_name, {})
    selected_model = model or provider_cfg.get("default_model") or provider_cfg.get("model")
    provider = build_provider(provider_cfg, model=selected_model)
    return provider, selected_model


def _strip_code_fences(text: str) -> str:
    stripped = (text or "").strip()
    if stripped.startswith("```"):
        lines = stripped.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        stripped = "\n".join(lines)
    return stripped.strip()


def _planner_system_prompt(*, is_repair: bool) -> str:
    if is_repair:
        return (
            "# System Prompt - TaskGraph v3 Planner Repair\n\n"
            "你是「TaskGraph v3 Planner 修復器」。\n"
            "你只做任務拆解與圖定義修復，不做 agent/assignment/persona。\n"
            "請根據錯誤原因修正上一版 GraphDefinition，並重新輸出：\n"
            "1. ```json ...```：可被 Amon TaskGraph v3 parser/validator 接受的 GraphDefinition JSON\n"
            "2. ```mermaid ...```：與 JSON 對應的 Mermaid flowchart\n\n"
            "硬性規則：\n"
            "- 第 1 個 TASK 必須是「概念對齊」。\n"
            "- 後續不得重複同質概念調研節點。\n"
            "- node.title 不得為空；若原本會是 None/空白，必須重寫成 <=10 個中文漢字的完整標題。\n"
            "- 嚴禁輸出任何 agent/persona/assignment/owner。\n"
            "- 除這兩段 code block 外不得輸出其他文字。\n"
        )
    return (
        "# System Prompt - TaskGraph v3 Planner（只做任務拆解與圖定義；不做 agent/assignment）\n\n"
        "你是「TaskGraph v3 Planner」。\n"
        "目標：把使用者任務拆解成 TODO 子任務，並輸出可執行的 TaskGraph v3 圖定義：\n"
        "(1) GraphDefinition JSON\n"
        "(2) 對應 Mermaid flowchart\n\n"
        "範圍限制（硬性）：\n"
        "- 你只做「任務/步驟」規劃與 skill/tool 選擇。\n"
        "- 嚴禁輸出任何 agent/persona/assignment/指派/審查團等內容；也不要填 owner。\n"
        "- 輸出 JSON 必須可通過 Pydantic GraphDefinition 驗證：extra=\"forbid\"、所有 id 必須唯一、邊與 children 引用必須存在。\n\n"
        "固定第一步（硬性）：\n"
        "- 第 1 個 TASK 節點永遠是：title=\"概念對齊\"\n"
        "- 內容：上網查詢關鍵概念定義、背景知識、常見作法/風險、關鍵名詞對照。\n"
        "- 後續不得再產生語意高度重複的概念/背景調研節點；除非是全新領域，且需在 constraints 寫明「新領域補充調研」理由。\n\n"
        "標題規則（硬性）：\n"
        "- 每個 node.title 必須非空。\n"
        "- 若原本會產生 None/空白 title，必須改寫成 <=10 個中文漢字、語意完整的標題句，不可單純截斷。\n\n"
        "只允許的節點/邊/模式（enum）：\n"
        "- NodeType：TASK | GROUP | GATE | ARTIFACT\n"
        "- EdgeType：CONTROL | DATA\n"
        "- ControlEdgeKind：DEPENDS_ON | SOFT_DEPENDS | ROUTE\n"
        "- DataEdgeKind：PRODUCES | CONSUMES | MAPS\n"
        "- ExecutionMode：SINGLE | PARALLEL_MAP | RECURSIVE\n\n"
        "規劃準則（planner 決策規則）：\n"
        "- 節點粒度是子任務，不是功能清單或單一工具操作。\n"
        "- 用 DEPENDS_ON 建立主要依賴；只有真的需要分支時才使用 GATE + ROUTE。\n"
        "- 每個 TASK 至少要有 objective + definitionOfDone（>=2 條）+ 主要 skillBindings（PRIMARY）。\n"
        "- 若產出需要被下游使用，優先建立 ARTIFACT node 與 PRODUCES/CONSUMES，或用 MAPS 明確傳遞 vars/ports。\n"
        "- 只有在真的有外部呼叫量、事件量或即時性需求時才設定 rateLimit/streamLimit。\n\n"
        "輸出格式（硬性，違者視為失敗）：\n"
        "- 只輸出兩段 code block：\n"
        "  1) ```json ...```：GraphDefinition（純 JSON、無註解、雙引號）\n"
        "  2) ```mermaid ...```：對應 Mermaid flowchart\n"
        "- 除這兩段外不得輸出任何其他文字。\n"
    )


def _planner_user_prompt(
    *,
    message: str,
    available_tools: list[dict[str, Any]] | None,
    available_skills: list[dict[str, Any]] | None,
    repair_error: str | None,
    previous_raw: str | None,
) -> str:
    skills_json = json.dumps(_normalize_available_skills(available_skills), ensure_ascii=False, indent=2)
    tools_json = json.dumps(_normalize_available_tools(available_tools), ensure_ascii=False, indent=2)
    sections = [
        "# Planner User Prompt（Template）",
        "",
        "任務描述：",
        message,
        "",
        "約束/偏好（可留空）：",
        "- 交付物（想要哪些 artifacts/ports）：",
        "",
        "- 技術/平台限制（例如 Web / Unity / Three.js / GPU / 不可用 X）：",
        "",
        "- 品質目標（例如 FPS、延遲、成本上限、安全需求）：",
        "",
        "- 時程/里程碑（如果有）：",
        "",
        "可用 Skills（如未提供，你可用 mock skillId，但必須合理且一致）：",
        skills_json,
        "",
        "可用 Tools（如未提供，你可用 mock toolId 放在 skillBindings.config.tools）：",
        tools_json,
        "",
        "輸出要求（重申）：",
        "- 第 1 個 TASK 必須是「概念對齊」，且使用 web/search 類工具做概念查詢。",
        "- 後續不得再出現同質概念調研節點。",
        "- node.title 不得為空；若原本會是 None，改寫成 <=10 個中文漢字標題句（不可截斷）。",
        "- 不得提 agent/persona/assignment/指派。",
        "- 僅輸出兩段 code block：GraphDefinition JSON + Mermaid。",
    ]
    if repair_error:
        sections.extend(
            [
                "",
                "修復要求：",
                repair_error,
                "",
                "上一版輸出：",
                previous_raw or "",
            ]
        )
    return "\n".join(sections)


def _normalize_available_tools(available_tools: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for item in available_tools or []:
        if not isinstance(item, dict):
            continue
        tool_name = str(item.get("name") or item.get("tool_name") or "")
        result.append(
            {
                "toolId": tool_name,
                "name": tool_name,
                "description": str(item.get("description") or item.get("when_to_use") or ""),
                "inputSchema": item.get("input_schema") or item.get("args_schema_hint") or {},
            }
        )
    return result


def _normalize_available_skills(available_skills: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for item in available_skills or []:
        if not isinstance(item, dict):
            continue
        skill_name = str(item.get("name") or "")
        result.append(
            {
                "skillId": skill_name,
                "name": skill_name,
                "description": str(item.get("description") or ""),
                "targets": item.get("targets") or item.get("inject_to") or [],
            }
        )
    return result


def _minimal_plan(message: str) -> GraphDefinition:
    return GraphDefinition(
        id="planner-fallback",
        version="taskgraph.v3",
        name="Fallback Planner Graph",
        nodes=[
            TaskNode(
                id="concept_alignment",
                title="概念對齊",
                task_spec=TaskSpec(
                    executor="agent",
                    agent=AgentTaskConfig(
                        prompt=(
                            f"任務：{message}\n"
                            "先做概念對齊，整理關鍵名詞定義、背景知識、常見作法、風險與後續規劃注意事項。"
                        ),
                        instructions="先完成概念對齊，再把摘要提供給下游規劃節點。",
                    ),
                    artifacts=[
                        ArtifactOutput(
                            name="concept_summary",
                            media_type="text/markdown",
                            description="概念對齊摘要",
                            required=True,
                        )
                    ],
                    display=TaskDisplayMetadata(
                        label="概念對齊",
                        summary="先查清關鍵概念與風險，再開始後續規劃。",
                        todo_hint="完成概念摘要、風險與名詞對照。",
                        tags=["concept_alignment", "fallback"],
                    ),
                    runnable=True,
                ),
            ),
            ArtifactNode(id="artifact-concept-summary", title="docs/concept_alignment.md"),
            TaskNode(
                id="task-1",
                title="初版規劃",
                task_spec=TaskSpec(
                    executor="agent",
                    agent=AgentTaskConfig(
                        prompt=message,
                        instructions="請延續前置概念對齊結果，產出最小可行 TODO 與交付骨架。",
                    ),
                    artifacts=[ArtifactOutput(name="todo", media_type="text/markdown", description="最小任務清單", required=True)],
                    display=TaskDisplayMetadata(
                        label="初版規劃",
                        summary="根據概念摘要切出最小可執行任務骨架。",
                        todo_hint="產出初版 TODO；標註依賴、輸出與待補資訊。",
                        tags=["planning", "fallback"],
                    ),
                    runnable=True,
                ),
            ),
            ArtifactNode(id="artifact-task-1-todo", title="docs/TODO.md"),
        ],
        edges=[
            GraphEdge(from_node="concept_alignment", to_node="artifact-concept-summary", edge_type="DATA", kind="PRODUCES"),
            GraphEdge(from_node="concept_alignment", to_node="task-1", edge_type="CONTROL", kind="DEPENDS_ON"),
            GraphEdge(from_node="task-1", to_node="artifact-task-1-todo", edge_type="DATA", kind="PRODUCES"),
        ],
    )


def _loads_graph_definition_from_response(text: str) -> GraphDefinition:
    json_text, mermaid = _extract_planner_response(text)
    graph = _loads_graph_definition(json_text)
    if mermaid:
        metadata = dict(graph.metadata or {})
        metadata["planner_mermaid"] = mermaid
        graph.metadata = metadata
    return graph


def _loads_graph_definition(text: str) -> GraphDefinition:
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"TaskGraph JSON 格式錯誤：{exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError("TaskGraph 必須是 object")
    graph = graph_definition_from_payload(payload)
    validate_graph_definition(graph)
    return graph


def _extract_planner_response(text: str) -> tuple[str, str | None]:
    raw = (text or "").strip()
    if not raw:
        raise ValueError("planner 輸出為空")

    json_block: str | None = None
    mermaid_block: str | None = None
    for match in _CODE_BLOCK_RE.finditer(raw):
        lang = (match.group("lang") or "").strip().lower()
        content = (match.group("content") or "").strip()
        if json_block is None and (lang == "json" or content.startswith("{")):
            json_block = content
            continue
        if mermaid_block is None and lang == "mermaid":
            mermaid_block = content

    if json_block is None:
        stripped = _strip_code_fences(raw)
        json_block = stripped if stripped.startswith("{") else raw
    return json_block.strip(), mermaid_block.strip() if mermaid_block else None


def _coerce_node(raw: Any):
    if not isinstance(raw, dict):
        raise ValueError("node 必須是 object")
    node_id = str(raw.get("id") or "")
    node_type = str(raw.get("node_type") or "").upper()
    title = str(raw.get("title") or "")
    if node_type == "TASK":
        spec_raw = raw.get("taskSpec")
        if not isinstance(spec_raw, dict):
            raise ValueError(f"TASK node 必須包含 taskSpec：{node_id}")
        return TaskNode(
            id=node_id,
            title=title,
            execution=str(raw.get("execution") or "SINGLE"),
            execution_config=raw.get("executionConfig") if isinstance(raw.get("executionConfig"), dict) else None,
            task_spec=task_spec_from_payload(spec_raw),
            task_boundaries=[str(item) for item in (raw.get("taskBoundaries") or [])] if isinstance(raw.get("taskBoundaries"), list) else None,
            guardrails=raw.get("guardrails") if isinstance(raw.get("guardrails"), dict) else None,
        )
    if node_type == "ARTIFACT":
        return ArtifactNode(id=node_id, title=title)
    if node_type == "GROUP":
        return GroupNode(id=node_id, title=title, children=[str(item) for item in (raw.get("children") or [])])
    if node_type == "GATE":
        routes = []
        for item in raw.get("routes") or []:
            if not isinstance(item, dict):
                raise ValueError(f"gate route 必須是 object：{node_id}")
            routes.append(GateRoute(on_outcome=str(item.get("onOutcome") or ""), to_node=str(item.get("toNode") or "")))
        return GateNode(id=node_id, title=title, routes=routes)
    raise ValueError(f"不支援的 node_type：{node_type or '<empty>'}")


def _coerce_edge(raw: Any) -> GraphEdge:
    if not isinstance(raw, dict):
        raise ValueError("edge 必須是 object")
    return GraphEdge(
        from_node=str(raw.get("from") or raw.get("from_node") or ""),
        to_node=str(raw.get("to") or raw.get("to_node") or ""),
        edge_type=str(raw.get("edge_type") or "CONTROL"),
        kind=str(raw.get("kind") or "next"),
    )
