from __future__ import annotations

import json
from typing import Any

TEAM_ROLE_PROTOTYPES: list[dict[str, Any]] = [
    {
        "key": "product_strategist",
        "name": "林曜廷",
        "role": "首席產品策略師",
        "description": "擅長把模糊目標拆成可交付的產品策略與優先級。",
        "focus": ["需求拆解", "價值排序", "風險假設"],
        "methodology": "MECE, JTBD, Outcome-driven Planning",
        "instructions": "先釐清目標與限制，再把任務切成可驗收的子問題，避免空泛敘述。",
    },
    {
        "key": "system_architect",
        "name": "顧承翰",
        "role": "系統架構師",
        "description": "專長是把流程與元件邊界定清楚，避免架構債擴散。",
        "focus": ["系統邊界", "依賴關係", "可維護性"],
        "methodology": "C4, ADR, Evolutionary Architecture",
        "instructions": "先守住相依邊界與前向相容，再討論重構深度與抽象。",
    },
    {
        "key": "research_analyst",
        "name": "沈可安",
        "role": "研究分析師",
        "description": "擅長快速整理來源、建立比較框架並萃取可引用證據。",
        "focus": ["來源比對", "證據鏈", "關鍵洞察"],
        "methodology": "Evidence Matrix, Comparative Analysis",
        "instructions": "每個結論都要對應證據或可驗證理由，避免憑印象下判斷。",
    },
    {
        "key": "fullstack_engineer",
        "name": "周柏宇",
        "role": "全端實作工程師",
        "description": "擅長把設計快速落地成可測試、可驗證的實作。",
        "focus": ["程式實作", "整合點", "驗證流程"],
        "methodology": "Vertical Slice, Test-first Hardening",
        "instructions": "優先做最小可交付改動，避免擴散到非問題區域。",
    },
    {
        "key": "ux_content_designer",
        "name": "葉庭瑜",
        "role": "UX 與內容設計師",
        "description": "擅長把複雜資訊整理成易讀、可操作的互動與內容結構。",
        "focus": ["資訊架構", "操作流程", "文字清晰度"],
        "methodology": "Content-first UX, Progressive Disclosure",
        "instructions": "任何輸出都要兼顧結構、可讀性與實際操作成本。",
    },
    {
        "key": "risk_auditor",
        "name": "許明哲",
        "role": "風險與品質稽核師",
        "description": "專門找出規格缺口、驗證盲點與實作風險。",
        "focus": ["驗收條件", "例外路徑", "品質風險"],
        "methodology": "Red Team Review, Failure Mode Analysis",
        "instructions": "審核時採高標準，必須點出具體缺口與補強方式。",
    },
]

TEAMWORK_SYSTEM_PROMPTS = {
    "role_factory": (
        "你現在是【頂尖人才獵頭與組織架構師】(Role Factory)。\n\n"
        "核心任務：根據專案經理拆解的任務與技能需求，設計具備世界級專業水準的專家角色。\n"
        "人設生成規範：\n"
        "1. 每個角色必須具備資深領域背景與清楚的方法論。\n"
        "2. 角色描述要包含工作風格、專業標籤、過往成就與可落地指令。\n"
        "3. 優先沿用既有角色原型；若不足，再做最小必要調整。\n"
        "4. 語系一律使用繁體中文。\n"
        "5. 若要求 JSON，必須只輸出合法 JSON。"
    ),
    "project_manager": (
        "你現在是【資深首席專案經理】(Chief Project Manager)。\n\n"
        "任務規劃階段：將複雜目標轉成可執行、可驗收、具先後關係的子任務。\n"
        "你必須做到：邏輯拆解、專業分工、具體描述、明確風險與交付標準。\n\n"
        "最終整合階段：輸出董事會級別的專業總結，內容需有結構、洞察、風險與執行路徑。\n"
        "所有輸出使用繁體中文；若要求 JSON，必須只輸出合法 JSON。"
    ),
    "project_member": (
        "你現在是【專案核心成員】(Project Member)。\n\n"
        "執行要求：\n"
        "1. 深度代入被分派的人設與方法論。\n"
        "2. 產出必須具備專業深度、可驗證性與實際執行價值。\n"
        "3. 不可只給泛泛建議，必須說明觀察、判斷理由、成果與評估方式。\n"
        "4. 若要求 JSON，必須只輸出合法 JSON。"
    ),
    "auditor": (
        "你現在是【資深行業稽核專家】。\n\n"
        "稽核標準：\n"
        "1. 專業嚴謹性：內容是否具備該領域應有的深度。\n"
        "2. 邏輯一致性：是否完整、無矛盾且能對應任務要求。\n"
        "3. 可驗證性：是否有可檢查的成果、依據與後續行動。\n"
        "4. 只要不夠完整或空泛，就必須退回並提出具體補強建議。\n"
        "若要求 JSON，必須只輸出合法 JSON。"
    ),
    "committee_member": (
        "你現在是【總驗收委員會成員：業界權威】。\n\n"
        "審核邏輯：\n"
        "1. 零容忍空洞內容、過度條列、缺乏專業深度與未回應風險的輸出。\n"
        "2. 只有在內容具備實戰價值、邏輯完整且交付標準明確時，才可全案通過。\n"
        "3. 即使整體品質不差，也要主動找出潛在風險與補強空間。\n"
        "若要求 JSON，必須只輸出合法 JSON。"
    ),
}

TEAMWORK_EXECUTION_SYSTEM_PROMPT = (
    TEAMWORK_SYSTEM_PROMPTS["role_factory"]
    + "\n\n"
    + TEAMWORK_SYSTEM_PROMPTS["project_member"]
    + "\n\n"
    + TEAMWORK_SYSTEM_PROMPTS["auditor"]
    + "\n\n你必須在單一回合完成 Teamworks 子任務流程：先做角色工廠指派，再做專案成員執行，最後做稽核。"
)


def team_role_prototypes_json() -> str:
    return json.dumps(TEAM_ROLE_PROTOTYPES, ensure_ascii=False, indent=2)


def build_single_graph_payload() -> dict[str, Any]:
    return {
        "nodes": [
            {
                "id": "single_task",
                "node_type": "TASK",
                "title": "Single Task",
                "taskSpec": {
                    "executor": "agent",
                    "agent": {
                        "prompt": "${prompt}",
                    },
                    "display": {"label": "Single", "summary": "單節點任務", "todoHint": "single", "tags": ["single"]},
                },
            },
            {
                "id": "single_output",
                "node_type": "TASK",
                "title": "Write Single Output",
                "taskSpec": {
                    "executor": "tool",
                    "tool": {
                        "tools": [
                            {
                                "name": "artifacts.write_text",
                                "args": {
                                    "path": "docs/single_${run_id}.md",
                                    "content": "${single_response}",
                                },
                            }
                        ]
                    },
                    "inputBindings": [
                        {"source": "upstream", "key": "single_response", "fromNode": "single_task", "port": "raw"}
                    ],
                    "display": {"label": "Write", "summary": "寫入單節點輸出", "todoHint": "write", "tags": ["single"]},
                },
            },
        ],
        "edges": [
            {"from": "single_task", "to": "single_output", "edge_type": "CONTROL", "kind": "DEPENDS_ON"}
        ],
    }


def build_self_critique_graph_payload() -> dict[str, Any]:
    return {
        "nodes": [
            {
                "id": "draft",
                "node_type": "TASK",
                "title": "Draft",
                "taskSpec": {
                    "executor": "agent",
                    "agent": {
                        "prompt": "任務：${prompt}\n\n請先產出可被嚴格審閱的完整草稿。",
                    },
                    "display": {"label": "Draft", "summary": "產出初稿", "todoHint": "draft", "tags": ["self_critique"]},
                },
            },
            {
                "id": "draft_output",
                "node_type": "TASK",
                "title": "Write Draft",
                "taskSpec": {
                    "executor": "tool",
                    "tool": {
                        "tools": [
                            {
                                "name": "artifacts.write_text",
                                "args": {"path": "${draft_path}", "content": "${draft_text}"},
                            }
                        ]
                    },
                    "inputBindings": [
                        {"source": "upstream", "key": "draft_text", "fromNode": "draft", "port": "raw"}
                    ],
                    "display": {"label": "Write Draft", "summary": "寫入草稿", "todoHint": "write draft", "tags": ["self_critique"]},
                },
            },
            {
                "id": "reviews_map",
                "node_type": "TASK",
                "title": "Parallel Reviews",
                "execution": "PARALLEL_MAP",
                "executionConfig": {"items": list(range(1, 11)), "maxConcurrency": 4, "resultParser": "json"},
                "outputContract": {
                    "ports": [
                        {
                            "name": "items",
                            "extractor": "json",
                            "typeRef": "array",
                            "jsonSchema": {"type": "array"},
                        }
                    ]
                },
                "taskSpec": {
                    "executor": "agent",
                    "agent": {
                        "prompt": (
                            "你是 Reviewer ${map_item}，請嚴格評論以下草稿，指出缺口並提出具體改善建議。"
                            "\n\n草稿：\n${draft_text}\n\n"
                            "只輸出 JSON：{\"review_id\":${map_item},\"review_markdown\":\"...\"}"
                        ),
                    },
                    "inputBindings": [
                        {"source": "upstream", "key": "draft_text", "fromNode": "draft", "port": "raw"}
                    ],
                    "display": {"label": "Reviews", "summary": "平行評論草稿", "todoHint": "reviews", "tags": ["self_critique"]},
                },
            },
            {
                "id": "write_reviews",
                "node_type": "TASK",
                "title": "Write Reviews",
                "execution": "PARALLEL_MAP",
                "executionConfig": {
                    "itemsFrom": {"source": "upstream", "fromNode": "reviews_map", "port": "items"},
                    "maxConcurrency": 4,
                },
                "taskSpec": {
                    "executor": "tool",
                    "tool": {
                        "tools": [
                            {
                                "name": "artifacts.write_text",
                                "args": {
                                    "path": "${reviews_dir}/review_${map_item_review_id}.md",
                                    "content": "${map_item_review_markdown}",
                                },
                            }
                        ]
                    },
                    "display": {"label": "Write Reviews", "summary": "寫入評論檔", "todoHint": "persist reviews", "tags": ["self_critique"]},
                },
            },
            {
                "id": "final",
                "node_type": "TASK",
                "title": "Final Rewrite",
                "taskSpec": {
                    "executor": "agent",
                    "agent": {
                        "prompt": (
                            "你是 Writer，請整合草稿與所有評論，產出最終版本。"
                            "\n\n任務：${prompt}\n\n草稿：\n${draft_text}\n\nReviews(JSON)：\n${reviews_json}\n"
                        ),
                    },
                    "inputBindings": [
                        {"source": "upstream", "key": "draft_text", "fromNode": "draft", "port": "raw"},
                        {"source": "upstream", "key": "reviews_json", "fromNode": "reviews_map", "port": "raw"},
                    ],
                    "display": {"label": "Final", "summary": "整合最終稿", "todoHint": "rewrite", "tags": ["self_critique"]},
                },
            },
            {
                "id": "final_output",
                "node_type": "TASK",
                "title": "Write Final",
                "taskSpec": {
                    "executor": "tool",
                    "tool": {
                        "tools": [
                            {
                                "name": "artifacts.write_text",
                                "args": {"path": "${final_path}", "content": "${final_text}"},
                            }
                        ]
                    },
                    "inputBindings": [
                        {"source": "upstream", "key": "final_text", "fromNode": "final", "port": "raw"}
                    ],
                    "display": {"label": "Write Final", "summary": "寫入最終稿", "todoHint": "write final", "tags": ["self_critique"]},
                },
            },
        ],
        "edges": [
            {"from": "draft", "to": "draft_output", "edge_type": "CONTROL", "kind": "DEPENDS_ON"},
            {"from": "draft_output", "to": "reviews_map", "edge_type": "CONTROL", "kind": "DEPENDS_ON"},
            {"from": "reviews_map", "to": "write_reviews", "edge_type": "CONTROL", "kind": "DEPENDS_ON"},
            {"from": "write_reviews", "to": "final", "edge_type": "CONTROL", "kind": "DEPENDS_ON"},
            {"from": "final", "to": "final_output", "edge_type": "CONTROL", "kind": "DEPENDS_ON"},
        ],
    }


def build_team_graph_payload() -> dict[str, Any]:
    return {
        "nodes": [
            {
                "id": "write_role_prototypes",
                "node_type": "TASK",
                "title": "Write Role Prototypes",
                "taskSpec": {
                    "executor": "tool",
                    "tool": {
                        "tools": [
                            {
                                "name": "artifacts.write_text",
                                "args": {
                                    "path": "docs/roles/team_role_prototypes.json",
                                    "content": "${team_role_prototypes_json}",
                                },
                            }
                        ]
                    },
                    "display": {"label": "Role Prototypes", "summary": "寫入團隊角色原型", "todoHint": "roles", "tags": ["team"]},
                },
            },
            {
                "id": "pm_todo",
                "node_type": "TASK",
                "title": "PM TODO",
                "taskSpec": {
                    "executor": "agent",
                    "agent": {
                        "systemPrompt": TEAMWORK_SYSTEM_PROMPTS["project_manager"],
                        "prompt": (
                            "請先輸出 TODO.md，拆解任務並標記初始狀態都為 [ ]。\n"
                            "必須包含 Step0：檢查專案 docs 資料夾中的遺留文件是否可接續。\n"
                            "第一行必須是『專案經理：』，第二行起列出 todo list。\n"
                            "若某步需要角色工廠，請直接標示『(向角色工廠申請人設中)』。\n\n"
                            "任務：${prompt}\n\n可接續資料摘要：\n${continuation_context}\n"
                        ),
                    },
                    "display": {"label": "PM TODO", "summary": "產生團隊 TODO", "todoHint": "todo", "tags": ["team", "pm"]},
                },
            },
            {
                "id": "write_todo",
                "node_type": "TASK",
                "title": "Write TODO",
                "taskSpec": {
                    "executor": "tool",
                    "tool": {
                        "tools": [
                            {"name": "artifacts.write_text", "args": {"path": "docs/TODO.md", "content": "${todo_markdown}"}}
                        ]
                    },
                    "inputBindings": [{"source": "upstream", "key": "todo_markdown", "fromNode": "pm_todo", "port": "raw"}],
                    "display": {"label": "Write TODO", "summary": "寫入 TODO.md", "todoHint": "persist todo", "tags": ["team"]},
                },
            },
            {
                "id": "pm_log_bootstrap",
                "node_type": "TASK",
                "title": "PM Bootstrap Log",
                "taskSpec": {
                    "executor": "agent",
                    "agent": {
                        "systemPrompt": TEAMWORK_SYSTEM_PROMPTS["project_manager"],
                        "prompt": (
                            "請建立 ProjectManager.md 的啟動紀錄，內容必須包含：決策理由、任務分派策略、風險控管、"
                            "與為何採用 Teamworks 流程。\n"
                            "輸出每段前請標註『專案經理：』。\n\n目前 TODO：\n${todo_markdown}\n\n任務：${prompt}\n"
                        ),
                    },
                    "inputBindings": [{"source": "upstream", "key": "todo_markdown", "fromNode": "pm_todo", "port": "raw"}],
                    "display": {"label": "PM Log", "summary": "建立啟動紀錄", "todoHint": "bootstrap log", "tags": ["team", "pm"]},
                },
            },
            {
                "id": "write_pm_log",
                "node_type": "TASK",
                "title": "Write PM Log",
                "taskSpec": {
                    "executor": "tool",
                    "tool": {
                        "tools": [
                            {
                                "name": "artifacts.write_text",
                                "args": {"path": "docs/ProjectManager.md", "content": "${pm_log_text}"},
                            }
                        ]
                    },
                    "inputBindings": [{"source": "upstream", "key": "pm_log_text", "fromNode": "pm_log_bootstrap", "port": "raw"}],
                    "display": {"label": "Write PM Log", "summary": "寫入 ProjectManager.md", "todoHint": "persist log", "tags": ["team"]},
                },
            },
            {
                "id": "pm_plan",
                "node_type": "TASK",
                "title": "PM Plan",
                "taskSpec": {
                    "executor": "agent",
                    "agent": {
                        "systemPrompt": TEAMWORK_SYSTEM_PROMPTS["project_manager"],
                        "prompt": (
                            "請根據任務拆解為 tasks JSON。必須只輸出合法 JSON。\n"
                            "格式：{\"tasks\":[{\"task_id\":\"T1\",\"title\":\"...\",\"role\":\"...\","
                            "\"description\":\"...\",\"requiredCapabilities\":[\"...\"],\"role_assignment_reason\":\"...\"}]}\n"
                            "規則：\n"
                            "1. 任務數量控制在 2 到 5 個。\n"
                            "2. 每個 task 都要有明確角色與能力需求。\n"
                            "3. 優先從以下角色原型分派；不足時再最小化擴充。\n"
                            "${team_role_prototypes_json}\n\n"
                            "任務：${prompt}\n"
                        ),
                    },
                    "display": {"label": "PM Plan", "summary": "拆解子任務", "todoHint": "plan", "tags": ["team", "pm"]},
                },
            },
            {
                "id": "write_team_plan",
                "node_type": "TASK",
                "title": "Write Team Plan",
                "taskSpec": {
                    "executor": "tool",
                    "tool": {
                        "tools": [
                            {
                                "name": "artifacts.write_text",
                                "args": {"path": "docs/team_plan_${run_id}.json", "content": "${team_plan_json}"},
                            }
                        ]
                    },
                    "inputBindings": [{"source": "upstream", "key": "team_plan_json", "fromNode": "pm_plan", "port": "raw"}],
                    "display": {"label": "Write Plan", "summary": "寫入團隊規劃", "todoHint": "persist plan", "tags": ["team"]},
                },
            },
            {
                "id": "write_tasks_json",
                "node_type": "TASK",
                "title": "Write Tasks JSON",
                "taskSpec": {
                    "executor": "tool",
                    "tool": {
                        "tools": [
                            {
                                "name": "artifacts.write_text",
                                "args": {"path": "docs/tasks.json", "content": "${tasks_json}"},
                            }
                        ]
                    },
                    "inputBindings": [{"source": "upstream", "key": "tasks_json", "fromNode": "pm_plan", "port": "raw"}],
                    "display": {"label": "Write Tasks", "summary": "寫入 tasks.json", "todoHint": "persist tasks", "tags": ["team"]},
                },
            },
            {
                "id": "task_teamwork_map",
                "node_type": "TASK",
                "title": "Teamworks Task Execution",
                "execution": "PARALLEL_MAP",
                "executionConfig": {
                    "itemsFrom": {"source": "upstream", "fromNode": "pm_plan", "port": "raw", "jsonPath": "tasks"},
                    "maxConcurrency": 2,
                    "resultParser": "json",
                },
                "outputContract": {
                    "ports": [
                        {
                            "name": "items",
                            "extractor": "json",
                            "typeRef": "array",
                            "jsonSchema": {"type": "array"},
                        }
                    ]
                },
                "taskSpec": {
                    "executor": "agent",
                    "agent": {
                        "systemPrompt": TEAMWORK_EXECUTION_SYSTEM_PROMPT,
                        "prompt": (
                            "請完成單一子任務的 Teamworks 流程，並只輸出合法 JSON。\n"
                            "子任務：${map_item_title}\n"
                            "角色：${map_item_role}\n"
                            "描述：${map_item_description}\n"
                            "能力需求：${map_item_requiredCapabilities}\n"
                            "角色分派理由：${map_item_role_assignment_reason}\n\n"
                            "既有角色原型：\n${team_role_prototypes_json}\n\n"
                            "請依序完成：\n"
                            "1. Role Factory：選出或微調最適合的人設 persona。\n"
                            "2. Project Member：依 persona 完成任務產出，需包含觀察、判斷理由、資料來源引述、成果與評估指標。\n"
                            "3. Auditor：審核該成果是否可通過，若不通過要給具體 feedback。\n\n"
                            "輸出格式："
                            "{\"task_id\":\"${map_item_task_id}\",\"title\":\"${map_item_title}\",\"role\":\"${map_item_role}\","
                            "\"description\":\"${map_item_description}\",\"persona\":{...},\"role_factory_markdown\":\"...\","
                            "\"result_markdown\":\"...\",\"audit\":{\"status\":\"APPROVED|REJECTED\",\"feedback\":\"...\"},"
                            "\"status\":\"done|rejected\"}"
                        ),
                    },
                    "display": {"label": "Task Teamwork", "summary": "平行執行團隊任務", "todoHint": "parallel execute", "tags": ["team", "parallel"]},
                },
            },
            {
                "id": "materialize_task_artifacts",
                "node_type": "TASK",
                "title": "Write Task Artifacts",
                "execution": "PARALLEL_MAP",
                "executionConfig": {
                    "itemsFrom": {"source": "upstream", "fromNode": "task_teamwork_map", "port": "raw"},
                    "maxConcurrency": 3,
                },
                "taskSpec": {
                    "executor": "tool",
                    "tool": {
                        "tools": [
                            {
                                "name": "artifacts.write_text",
                                "args": {
                                    "path": "docs/tasks/${map_item_task_id}/persona.json",
                                    "content": "${map_item_persona}",
                                },
                            },
                            {
                                "name": "artifacts.write_text",
                                "args": {
                                    "path": "docs/tasks/${map_item_task_id}/role_factory.md",
                                    "content": "${map_item_role_factory_markdown}",
                                },
                            },
                            {
                                "name": "artifacts.write_text",
                                "args": {
                                    "path": "docs/tasks/${map_item_task_id}/result.md",
                                    "content": "${map_item_result_markdown}",
                                },
                            },
                            {
                                "name": "artifacts.write_text",
                                "args": {
                                    "path": "docs/audits/${map_item_task_id}.json",
                                    "content": "${map_item_audit}",
                                },
                            },
                        ]
                    },
                    "display": {"label": "Task Artifacts", "summary": "寫入每個子任務產物", "todoHint": "persist task outputs", "tags": ["team"]},
                },
            },
            {
                "id": "audit_committee_role_factory",
                "node_type": "TASK",
                "title": "Committee Personas",
                "taskSpec": {
                    "executor": "agent",
                    "agent": {
                        "systemPrompt": TEAMWORK_SYSTEM_PROMPTS["role_factory"],
                        "prompt": (
                            "請為最終稽核會建立 3 位稽核員人設，輸出 JSON。"
                            "格式：{\"committee\":[{\"name\":\"...\",\"role\":\"...\",\"focus\":\"...\",\"instructions\":\"...\"}]}"
                            "，視角需涵蓋品質、風險、可驗證性。\n\n"
                            "任務：${prompt}\n\n任務輸出摘要(JSON)：\n${team_outputs_json}\n"
                        ),
                    },
                    "inputBindings": [
                        {"source": "upstream", "key": "team_outputs_json", "fromNode": "task_teamwork_map", "port": "raw"}
                    ],
                    "display": {"label": "Committee Personas", "summary": "建立稽核會人設", "todoHint": "committee roles", "tags": ["team", "audit"]},
                },
            },
            {
                "id": "write_committee_roles",
                "node_type": "TASK",
                "title": "Write Committee Roles",
                "taskSpec": {
                    "executor": "tool",
                    "tool": {
                        "tools": [
                            {
                                "name": "artifacts.write_text",
                                "args": {
                                    "path": "docs/audits/committee_roles.json",
                                    "content": "${committee_roles_json}",
                                },
                            }
                        ]
                    },
                    "inputBindings": [
                        {"source": "upstream", "key": "committee_roles_json", "fromNode": "audit_committee_role_factory", "port": "raw"}
                    ],
                    "display": {"label": "Write Committee", "summary": "寫入稽核會人設", "todoHint": "persist committee", "tags": ["team"]},
                },
            },
            {
                "id": "audit_committee_gate",
                "node_type": "TASK",
                "title": "Committee Review",
                "taskSpec": {
                    "executor": "agent",
                    "agent": {
                        "systemPrompt": TEAMWORK_SYSTEM_PROMPTS["committee_member"],
                        "prompt": (
                            "你是稽核會，請審查全部任務是否可整體交付。"
                            "只輸出 JSON：{\"status\":\"APPROVED_ALL|REJECTED\",\"reason\":\"...\",\"actions\":[\"...\"]}\n\n"
                            "稽核會人設(JSON)：\n${committee_roles_json}\n\n"
                            "任務輸出摘要(JSON)：\n${team_outputs_json}\n"
                        ),
                    },
                    "inputBindings": [
                        {"source": "upstream", "key": "committee_roles_json", "fromNode": "audit_committee_role_factory", "port": "raw"},
                        {"source": "upstream", "key": "team_outputs_json", "fromNode": "task_teamwork_map", "port": "raw"},
                    ],
                    "display": {"label": "Committee Review", "summary": "總驗收審查", "todoHint": "committee review", "tags": ["team", "audit"]},
                },
            },
            {
                "id": "write_committee_decision",
                "node_type": "TASK",
                "title": "Write Committee Decision",
                "taskSpec": {
                    "executor": "tool",
                    "tool": {
                        "tools": [
                            {
                                "name": "artifacts.write_text",
                                "args": {
                                    "path": "docs/audits/committee_decision.json",
                                    "content": "${committee_decision_json}",
                                },
                            }
                        ]
                    },
                    "inputBindings": [
                        {"source": "upstream", "key": "committee_decision_json", "fromNode": "audit_committee_gate", "port": "raw"}
                    ],
                    "display": {"label": "Write Decision", "summary": "寫入委員會決議", "todoHint": "persist decision", "tags": ["team"]},
                },
            },
            {
                "id": "synthesis",
                "node_type": "TASK",
                "title": "Final Synthesis",
                "taskSpec": {
                    "executor": "agent",
                    "agent": {
                        "systemPrompt": TEAMWORK_SYSTEM_PROMPTS["project_manager"],
                        "prompt": (
                            "請彙整所有任務結果與審核，產出最終總結。\n"
                            "若 committee decision.status = APPROVED_ALL：\n"
                            "1. 開頭必須是 '# TeamworksGPT'\n"
                            "2. 第二行必須是 '## 我務必依照以下的【角色定義】 以及【工作流程】來完成任務'\n"
                            "3. 需說明已如何遵守 Step0~Step6，並註明稽核會全員通過。\n"
                            "4. 內容中要有具名段落：專案經理、角色工廠、專案成員、稽核會。\n\n"
                            "若 committee decision.status = REJECTED：\n"
                            "1. 第一行必須是『專案經理：任務分派為補強』\n"
                            "2. 明確列出未通過原因、補強任務與下一輪輸出要求。\n\n"
                            "任務：${prompt}\n\n委員會決議(JSON)：\n${committee_decision_json}\n\n"
                            "任務輸出摘要(JSON)：\n${team_outputs_json}\n"
                        ),
                    },
                    "inputBindings": [
                        {"source": "upstream", "key": "committee_decision_json", "fromNode": "audit_committee_gate", "port": "raw"},
                        {"source": "upstream", "key": "team_outputs_json", "fromNode": "task_teamwork_map", "port": "raw"},
                    ],
                    "display": {"label": "Synthesis", "summary": "產生最終交付", "todoHint": "final", "tags": ["team", "pm"]},
                },
            },
            {
                "id": "write_final",
                "node_type": "TASK",
                "title": "Write Final",
                "taskSpec": {
                    "executor": "tool",
                    "tool": {
                        "tools": [
                            {"name": "artifacts.write_text", "args": {"path": "docs/final.md", "content": "${final_text}"}}
                        ]
                    },
                    "inputBindings": [{"source": "upstream", "key": "final_text", "fromNode": "synthesis", "port": "raw"}],
                    "display": {"label": "Write Final", "summary": "寫入最終交付", "todoHint": "persist final", "tags": ["team"]},
                },
            },
        ],
        "edges": [
            {"from": "write_role_prototypes", "to": "pm_todo", "edge_type": "CONTROL", "kind": "DEPENDS_ON"},
            {"from": "pm_todo", "to": "write_todo", "edge_type": "CONTROL", "kind": "DEPENDS_ON"},
            {"from": "write_todo", "to": "pm_log_bootstrap", "edge_type": "CONTROL", "kind": "DEPENDS_ON"},
            {"from": "pm_log_bootstrap", "to": "write_pm_log", "edge_type": "CONTROL", "kind": "DEPENDS_ON"},
            {"from": "write_pm_log", "to": "pm_plan", "edge_type": "CONTROL", "kind": "DEPENDS_ON"},
            {"from": "pm_plan", "to": "write_team_plan", "edge_type": "CONTROL", "kind": "DEPENDS_ON"},
            {"from": "write_team_plan", "to": "write_tasks_json", "edge_type": "CONTROL", "kind": "DEPENDS_ON"},
            {"from": "write_tasks_json", "to": "task_teamwork_map", "edge_type": "CONTROL", "kind": "DEPENDS_ON"},
            {"from": "task_teamwork_map", "to": "materialize_task_artifacts", "edge_type": "CONTROL", "kind": "DEPENDS_ON"},
            {"from": "materialize_task_artifacts", "to": "audit_committee_role_factory", "edge_type": "CONTROL", "kind": "DEPENDS_ON"},
            {"from": "audit_committee_role_factory", "to": "write_committee_roles", "edge_type": "CONTROL", "kind": "DEPENDS_ON"},
            {"from": "write_committee_roles", "to": "audit_committee_gate", "edge_type": "CONTROL", "kind": "DEPENDS_ON"},
            {"from": "audit_committee_gate", "to": "write_committee_decision", "edge_type": "CONTROL", "kind": "DEPENDS_ON"},
            {"from": "write_committee_decision", "to": "synthesis", "edge_type": "CONTROL", "kind": "DEPENDS_ON"},
            {"from": "synthesis", "to": "write_final", "edge_type": "CONTROL", "kind": "DEPENDS_ON"},
        ],
    }
