"""LLM planner for generating TaskGraph v3 TODO graphs."""

from __future__ import annotations

import json
import logging
from pathlib import Path
import re
from typing import Any, Iterable, Protocol

from amon.config import ConfigLoader
from amon.events import emit_event
from amon.llm_request_log import append_llm_request, build_llm_request_payload
from amon.logging import log_event
from amon.models import build_provider

from amon.taskgraph3.payloads import AgentTaskConfig, ArtifactOutput, TaskDisplayMetadata, TaskSpec, task_spec_from_payload
from amon.taskgraph3.schema import ArtifactNode, GateNode, GateRoute, GraphDefinition, GraphEdge, GroupNode, TaskNode, validate_graph_definition
from amon.taskgraph3.validate import graph_definition_from_payload

logger = logging.getLogger(__name__)

_CODE_BLOCK_RE = re.compile(r"```(?P<lang>[^\n`]*)\n(?P<content>.*?)```", re.DOTALL)
_MAX_TASK_NODES = 8
_PREFERRED_TASK_NODES = "4-6"
_CONCEPT_TASK_TOKENS = (
    "concept_alignment",
    "concept alignment",
    "概念對齊",
    "背景調研",
    "背景研究",
    "背景知識",
    "background research",
)
_SPEC_CLUSTER_TOKENS = (
    "requirements",
    "需求",
    "prd",
    "visual",
    "視覺",
    "architecture",
    "架構",
    "spec",
    "規格",
    "preset",
    "預設",
)
_PACKAGING_TOKENS = ("packaging", "release", "bundle", "交付", "打包", "封裝", "驗收")
_PLANNING_TASK_TOKENS = (
    "taskgraph_outline",
    "task outline",
    "todo outline",
    "todo",
    "wbs",
    "任務拆解",
    "待辦拆解",
    "問題拆解",
    "骨架規劃",
)
_PLANNER_INTERNAL_SKILL_TOKENS = (
    "problem-decomposer",
    "issue tree",
    "wbs",
    "問題拆解",
    "任務拆解",
    "待辦拆解",
    "task outline",
    "taskgraph_outline",
)
_REPAIRABLE_SEMANTIC_ISSUES = {
    "出現重複的概念對齊/背景調研 TASK，必須只保留 1 個。",
    "需求/PRD/架構/視覺/預設參數被切成過多獨立 TASK，必須合併為同一設計階段節點。",
    "打包交付/release 類 TASK 缺少前置依賴，不可作為前段 root。",
}


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
        repair_reason: str | None = None
        previous_raw = raw
        for _ in range(2):
            try:
                graph = _loads_graph_definition_from_response(previous_raw)
                fatal_issues = _fatal_semantic_plan_issues(graph)
                if not fatal_issues:
                    return graph
                repair_reason = "語義修復要求：\n- " + "\n- ".join(fatal_issues)
            except ValueError as exc:
                repair_reason = str(exc)
            previous_raw = _request_plan(
                client,
                selected_model,
                message=normalized,
                available_tools=available_tools,
                available_skills=available_skills,
                repair_error=repair_reason,
                previous_raw=previous_raw,
                project_path=project_path,
                project_id=project_id,
                run_id=run_id,
                thread_id=thread_id,
                request_id=request_id,
            )
        graph = _loads_graph_definition_from_response(previous_raw)
        fatal_issues = _fatal_semantic_plan_issues(graph)
        if fatal_issues:
            raise ValueError("planner 語義修復失敗：" + "; ".join(fatal_issues))
        return graph
    except Exception as exc:  # noqa: BLE001
        _record_planner_fallback(
            error=exc,
            project_id=project_id,
            run_id=run_id,
            thread_id=thread_id,
        )
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
            "1. ```json ...```：可被 Amon TaskGraph v3 parser/validator 接受的 GraphDefinition JSON\n\n"
            "硬性規則：\n"
            "- TASK 節點列表索引 0 的第一個 TASK 必須是「概念對齊」。\n"
            "- 「概念對齊」節點的 PRIMARY skillBindings 必須包含 concept-alignment。\n"
            "- planner 已經在圖外完成任務拆解；GraphDefinition 內不得再出現 TODO / 任務拆解 / task outline / WBS 類 TASK。\n"
            "- 後續不得重複同質概念調研節點。\n"
            f"- TASK 節點總數不得超過 {_MAX_TASK_NODES}，優先控制在 {_PREFERRED_TASK_NODES} 個；過細步驟要合併成較大的交付節點。\n"
            "- 根據上下文構成以及執行角色相似程度來切分。\n"
            "- 執行角色是任務的天然分界；若主執行者、權限、side effect、獨立審核或重跑需求不同，必須拆成不同 TASK。\n"
            "- 目前節點的上下文若近似於前一節點上下文加前一節點輸出，且只是連續推進同一目標，應與前一節點合併為單一 TASK，透過多個 artifact 表達不同產出。\n"
            "- 目前節點的上下文若只是前一節點上下文的嚴格子集合，且母節點只是等待子任務完成，應優先表達為 GROUP / children，而不是額外平鋪成兄弟 TASK。\n"
            "- 需求規格、PRD、系統架構、架構設計、視覺規格、預設參數若屬同一設計階段，必須合併成單一 TASK，透過多個 artifact 輸出，不可拆成多個連續規劃節點。\n"
            "- 打包交付 / release / bundle / 驗收只能出現在後段，必須帶明確前置依賴，不可成為概念對齊之後的直接 root。\n"
            "- 後續執行節點只負責完成當前交付，不可把整體問題再拆解一次，也不可重做概念對齊。\n"
            "- 問題拆解 / WBS / issue tree 類 skill 屬於 planner 內部能力；不要把這類 skill 放進任何 task 的 skillBindings。\n"
            "- Task 是可由單一主執行者直接完成、且有明確 objective 與 definitionOfDone 的工作單元。\n"
            "- Artifact 是 TASK 產出的文件、資料、程式碼、報告、規格或交付包；Artifact 不是執行工作，不可把「測試報告」「規格文件」「交付包」直接當成 TASK。\n"
            "- Milestone 是時點或狀態檢查，不是 TaskGraph v3 NodeType；不可建立 milestone node，也不可用 milestone 名稱取代真正工作。像「交付客戶」「核准通過」「上線完成」若只是狀態/時點，應改表達為驗收條件、artifact 完成或依賴關係。\n"
            "- 母任務更接近任務群組概念；若某上位節點只是在等所有子任務完成，應使用 GROUP，而不是再包一層沒有獨立工作的 TASK。\n"
            "- node.title 不得為空；若原本會是 None/空白，必須重寫成 <=10 個中文漢字的完整標題。\n"
            "- CONTROL 邊的方向必須是「前置節點 -> 依賴它的節點」，例如 concept_alignment -> design。\n"
            "- DATA/PRODUCES 必須是「產生者 -> artifact」；DATA/CONSUMES 必須是「artifact -> 使用它的節點」。\n"
            "- 嚴禁輸出任何 agent/persona/assignment/owner。\n"
            "- 壞例子：概念對齊 -> 背景調研 -> 需求規格 -> PRD -> 架構設計 -> 視覺規格 -> 預設參數 -> 打包交付。\n"
            "- 好例子：概念對齊 -> 設計定義（需求/PRD/架構/視覺/預設參數合併） -> 原型實作/內容產出 -> 打包交付。\n"
            "- UI 不使用 Mermaid；不要輸出 Mermaid，也不要輸出任何 JSON 之外的補充文字。\n"
        )
    return (
        "# System Prompt - TaskGraph v3 Planner（只做任務拆解與圖定義；不做 agent/assignment）\n\n"
        "你是「TaskGraph v3 Planner」。\n"
        "目標：把使用者任務拆解成 TODO 子任務，並輸出可執行的 TaskGraph v3 圖定義：\n"
        "(1) GraphDefinition JSON\n\n"
        "範圍限制（硬性）：\n"
        "- 你只做「任務/步驟」規劃與 skill/tool 選擇。\n"
        "- 嚴禁輸出任何 agent/persona/assignment/指派/審查團等內容；也不要填 owner。\n"
        "- 輸出 JSON 必須可通過 Pydantic GraphDefinition 驗證：extra=\"forbid\"、所有 id 必須唯一、邊與 children 引用必須存在。\n\n"
        "固定第一步（硬性）：\n"
        "- TASK 節點列表中的第 0 個節點永遠是：title=\"概念對齊\"\n"
        "- 內容：上網查詢關鍵概念定義、背景知識、常見作法/風險、關鍵名詞對照。\n"
        "- 此節點的 PRIMARY skillBindings 必須包含 concept-alignment。\n"
        "- planner 已在圖外完成拆題；graph 內不可再放 TODO / 任務拆解 / task outline / WBS 類節點。\n"
        "- 後續不得再產生語意高度重複的概念/背景調研節點；除非是全新領域，且需在 constraints 寫明「新領域補充調研」理由。\n\n"
        "步驟切分規範（硬性）：\n"
        f"- TASK 節點總數不得超過 {_MAX_TASK_NODES}；優先控制在 {_PREFERRED_TASK_NODES} 個。\n"
        "- 優先用「較大但可驗收」的交付節點，不要把同一階段拆成大量微步驟。\n"
        "- 根據上下文構成以及執行角色相似程度來切分。\n"
        "- 執行角色是任務的天然分界；若主執行者、權限、side effect、獨立審核或重跑需求不同，必須拆成不同 TASK。\n"
        "- 子任務的上文若只是母任務上文的子集合，拆分才有意義；如果目前節點上下文近似於前一節點上下文加前一節點輸出，且只是連續推進同一目標，應與前一節點合併。\n"
        "- 如果目前節點上下文只是前一節點上下文的嚴格子集合，且母節點只是等待全部子任務完成，應優先用 GROUP / children 表達，而不是額外平鋪成兄弟 TASK。\n"
        "- 同一設計階段內的需求規格、PRD、系統架構、架構設計、視覺規格、預設參數，應合併成 1 個 TASK，透過多個 artifacts 表達產出。\n"
        "- 後續 TASK 是執行節點，不是重新拆題節點；不可在任何 TASK 再做 TODO 分解、WBS、任務骨架規劃或概念對齊。\n"
        "- 打包交付 / release / bundle / 驗收必須位於後段，且要有明確依賴；不可直接接在概念對齊後面。\n\n"
        "節點辨識與邊界（硬性）：\n"
        "- Task 是可由單一主執行者直接完成、且有明確 objective 與 definitionOfDone 的工作單元。\n"
        "- Artifact 是被 TASK 產出、引用、審查或交付的資訊／檔案／程式碼／報告／規格；Artifact 不是執行工作，不可把「測試報告」「規格文件」「交付包」直接當成 TASK。\n"
        "- Milestone 是時點或狀態檢查，不是 TaskGraph v3 NodeType；不可建立 milestone node，也不可用 milestone 名稱取代真正工作。像「交付客戶」「核准通過」「上線完成」若只是狀態/時點，應改表達為驗收條件、artifact 完成或依賴關係。\n"
        "- 母任務其實更接近任務群組概念；若上位節點只是在等待所有子任務完成，應使用 GROUP。只有當上位節點需要主動整合全部子輸出時，才建立真正的 TASK。\n"
        "- 問題拆解 / WBS / issue tree 類 skill 屬於 planner 內部能力；不要把這類 skill 放進任何 task 的 skillBindings。\n\n"
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
        "- 用 DEPENDS_ON 建立主要依賴；CONTROL 邊方向固定是「前置節點 -> 依賴它的節點」，例如 concept_alignment -> 設計定義；只有真的需要分支時才使用 GATE + ROUTE。\n"
        "- 每個 TASK 至少要有 objective + definitionOfDone（>=2 條）+ 主要 skillBindings（PRIMARY）。\n"
        "- 若產出需要被下游使用，優先建立 ARTIFACT node；DATA/PRODUCES 方向固定是「產生者 -> artifact」，DATA/CONSUMES 方向固定是「artifact -> 使用它的節點」，或用 MAPS 明確傳遞 vars/ports。\n"
        "- 只有在真的有外部呼叫量、事件量或即時性需求時才設定 rateLimit/streamLimit。\n\n"
        "正反例（硬性參考）：\n"
        "- 壞例子：概念對齊 -> 背景調研 -> 需求規格 -> PRD -> 架構設計 -> 視覺規格 -> 預設參數 -> 打包交付。\n"
        "- 好例子：概念對齊 -> 設計定義（把需求/PRD/架構/視覺/預設參數合併成同一節點） -> 實作/內容產出 -> 打包交付。\n\n"
        "輸出格式（硬性，違者視為失敗）：\n"
        "- 只輸出一段 code block：\n"
        "  1) ```json ...```：GraphDefinition（純 JSON、無註解、雙引號）\n"
        "- UI 不使用 Mermaid；不要輸出 Mermaid，也不要輸出任何其他文字。\n"
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
        "- TASK 節點列表索引 0 的第一個 TASK 必須是「概念對齊」，且使用 web/search 類工具做概念查詢。",
        "- 「概念對齊」節點的 PRIMARY skillBindings 必須包含 concept-alignment。",
        "- planner 已在圖外完成拆題；graph 內不得再出現 TODO / 任務拆解 / task outline / WBS 類 TASK。",
        "- 後續不得再出現同質概念調研節點。",
        f"- TASK 節點總數不得超過 {_MAX_TASK_NODES}，優先控制在 {_PREFERRED_TASK_NODES} 個。",
        "- 同一設計階段的需求/PRD/系統架構/架構設計/視覺規格/預設參數要合併成較大的 TASK，不可拆成多個連續規劃節點。",
        "- 後續 TASK 只執行本節點交付，不可重做整體拆題或概念對齊。",
        "- 打包交付 / release / bundle / 驗收不得成為概念對齊後的直接 root，必須有明確前置依賴。",
        "- node.title 不得為空；若原本會是 None，改寫成 <=10 個中文漢字標題句（不可截斷）。",
        "- CONTROL/DEPENDS_ON 的方向固定是前置節點 -> 依賴它的節點，例如 concept_alignment -> design。",
        "- DATA/PRODUCES 的方向固定是產生者 -> artifact；DATA/CONSUMES 的方向固定是 artifact -> 使用它的節點。",
        "- 不得提 agent/persona/assignment/指派。",
        "- 僅輸出一段 json code block；不要輸出 Mermaid。",
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
        if _is_planner_internal_skill(item):
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


def _is_planner_internal_skill(item: dict[str, Any]) -> bool:
    parts = [
        str(item.get("name") or "").strip().lower(),
        str(item.get("description") or "").strip().lower(),
    ]
    targets = item.get("targets") or item.get("inject_to") or []
    if isinstance(targets, list):
        parts.extend(str(target).strip().lower() for target in targets)
    normalized = " ".join(part for part in parts if part)
    if not normalized:
        return False
    return any(token in normalized for token in _PLANNER_INTERNAL_SKILL_TOKENS)


def _semantic_plan_issues(graph: GraphDefinition) -> list[str]:
    task_nodes = [node for node in graph.nodes if isinstance(node, TaskNode)]
    issues: list[str] = []
    if len(task_nodes) > _MAX_TASK_NODES:
        issues.append(f"TASK 節點過多（{len(task_nodes)} > {_MAX_TASK_NODES}），必須合併成較大的交付步驟。")
    concept_nodes = [node for node in task_nodes if _is_concept_task(node)]
    if len(concept_nodes) > 1:
        issues.append("出現重複的概念對齊/背景調研 TASK，必須只保留 1 個。")
    planning_nodes = [node for node in task_nodes if node.id != "concept_alignment" and _is_planning_task(node)]
    if planning_nodes:
        issues.append("planner 已在圖外完成拆題，graph 內不得再出現 TODO / 任務拆解 / WBS 類 TASK。")
    spec_cluster_count = sum(1 for node in task_nodes if _is_spec_cluster_task(node))
    if spec_cluster_count >= 3:
        issues.append("需求/PRD/架構/視覺/預設參數被切成過多獨立 TASK，必須合併為同一設計階段節點。")
    incoming_dependencies = _incoming_dependency_count(graph)
    for node in task_nodes:
        if node.id == "concept_alignment":
            continue
        if _is_packaging_task(node) and incoming_dependencies.get(node.id, 0) == 0:
            issues.append("打包交付/release 類 TASK 缺少前置依賴，不可作為前段 root。")
            break
    return issues


def semantic_plan_issues(graph: GraphDefinition) -> list[str]:
    return _semantic_plan_issues(graph)


def _fatal_semantic_plan_issues(graph: GraphDefinition) -> list[str]:
    return [issue for issue in _semantic_plan_issues(graph) if issue not in _REPAIRABLE_SEMANTIC_ISSUES]


def _incoming_dependency_count(graph: GraphDefinition) -> dict[str, int]:
    incoming = {node.id: 0 for node in graph.nodes}
    for edge in graph.edges:
        if edge.edge_type not in {"CONTROL", "DATA"}:
            continue
        incoming[edge.to_node] = incoming.get(edge.to_node, 0) + 1
    return incoming


def _normalize_task_identity_text(node: TaskNode) -> str:
    parts = [
        node.id,
        node.title,
        node.task_spec.display.label if node.task_spec and node.task_spec.display else "",
        node.task_spec.display.summary if node.task_spec and node.task_spec.display else "",
        node.task_spec.display.todo_hint if node.task_spec and node.task_spec.display else "",
    ]
    return " ".join(str(item or "").strip().lower() for item in parts if str(item or "").strip())


def _normalize_task_text(node: TaskNode) -> str:
    parts = [
        _normalize_task_identity_text(node),
        node.task_spec.agent.prompt if node.task_spec and node.task_spec.agent else "",
        node.task_spec.agent.instructions if node.task_spec and node.task_spec.agent else "",
    ]
    return " ".join(str(item or "").strip().lower() for item in parts if str(item or "").strip())


def _is_concept_task(node: TaskNode) -> bool:
    normalized = _normalize_task_identity_text(node)
    return any(token in normalized for token in _CONCEPT_TASK_TOKENS)


def _is_spec_cluster_task(node: TaskNode) -> bool:
    normalized = _normalize_task_identity_text(node)
    return any(token in normalized for token in _SPEC_CLUSTER_TOKENS)


def _is_packaging_task(node: TaskNode) -> bool:
    normalized = _normalize_task_identity_text(node)
    return any(token in normalized for token in _PACKAGING_TOKENS)


def _is_planning_task(node: TaskNode) -> bool:
    normalized = _normalize_task_text(node)
    return any(token in normalized for token in _PLANNING_TASK_TOKENS)


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
                        skills=["concept-alignment"],
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
                title="任務執行",
                task_spec=TaskSpec(
                    executor="agent",
                    agent=AgentTaskConfig(
                        prompt=message,
                        instructions="請延續前置概念對齊結果，直接完成最小可行交付。",
                    ),
                    artifacts=[ArtifactOutput(name="todo", media_type="text/markdown", description="最小任務清單", required=True)],
                    display=TaskDisplayMetadata(
                        label="任務執行",
                        summary="根據概念摘要直接完成最小可行交付。",
                        todo_hint="完成最小交付，並標註依賴、輸出與待補資訊。",
                        tags=["execution", "fallback"],
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


def _record_planner_fallback(
    *,
    error: Exception,
    project_id: str | None,
    run_id: str | None,
    thread_id: str | None,
) -> None:
    error_text = str(error or "").strip() or error.__class__.__name__
    log_event(
        {
            "level": "WARNING",
            "event": "planner_fallback_minimal_plan",
            "project_id": project_id,
            "run_id": run_id,
            "thread_id": thread_id,
            "source": "planner_llm",
            "message": error_text[:600],
            "error_type": error.__class__.__name__,
        }
    )
    if project_id:
        emit_event(
            {
                "type": "planner_fallback_minimal_plan",
                "scope": "planning",
                "project_id": project_id,
                "actor": "system",
                "payload": {
                    "reason": error_text[:600],
                    "error_type": error.__class__.__name__,
                },
                "risk": "medium",
            }
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
