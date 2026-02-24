# PlanGraph / ExecGraph 兩層圖重構護欄（Phase 1 草案）

## 目標

在不破壞既有行為的前提下，將「規劃」與「執行」拆成兩層圖：

- **PlanGraph**：事務性 TODO 圖（描述要做什麼、為什麼做、約束是什麼）。
- **ExecGraph**：功能性執行圖（描述怎麼做、用哪些節點、實際執行順序）。

本文件為 **Phase 1 護欄文件**，先定義介面與相容策略；PlanGraph 實際編譯器於 Phase 2 實作。

## 分工與邊界

### PlanGraph（Transaction / Intent Layer）

- 聚焦於任務拆解、目標、驗收條件、依賴、風險、回滾點。
- 不直接綁定 runtime node 細節（例如 agent_task / write_file）。
- 可供審閱、預覽、簽核（`preview_only`）。

### ExecGraph（Execution / Runtime Layer）

- 聚焦於可執行節點、資料流、runtime 參數。
- 由現有 GraphRuntime 執行。
- 保持既有 JSON graph contract，確保向後相容。

## PlanGraph JSON Schema（Draft for Phase 2）

> 目前為草案 schema，用於跨團隊對齊；尚未在 runtime 強制驗證。

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "title": "PlanGraphDraft",
  "type": "object",
  "required": ["version", "plan_id", "goal", "tasks"],
  "properties": {
    "version": {"type": "string", "const": "plan-graph.v0.draft"},
    "plan_id": {"type": "string", "minLength": 1},
    "goal": {"type": "string", "minLength": 1},
    "context": {"type": "object", "additionalProperties": true},
    "constraints": {
      "type": "array",
      "items": {"type": "string"}
    },
    "tasks": {
      "type": "array",
      "minItems": 1,
      "items": {
        "type": "object",
        "required": ["id", "title"],
        "properties": {
          "id": {"type": "string", "minLength": 1},
          "title": {"type": "string", "minLength": 1},
          "depends_on": {
            "type": "array",
            "items": {"type": "string"}
          },
          "acceptance": {
            "type": "array",
            "items": {"type": "string"}
          },
          "rollback_hint": {"type": "string"}
        },
        "additionalProperties": true
      }
    },
    "metadata": {"type": "object", "additionalProperties": true}
  },
  "additionalProperties": true
}
```

## 編譯流程（PlanGraph -> ExecGraph）

1. 產生 PlanGraph（或由使用者提供）。
2. 驗證草案欄位完整性（Phase 2 強化為正式 validator）。
3. 編譯為 ExecGraph：
   - 映射 tasks -> runtime nodes
   - 保留必要 trace metadata（plan_id/task_id）
4. 交給既有 GraphRuntime 執行。

## 相容策略

- 預設仍走既有 ExecGraph 流程。
- 新增能力皆以 feature flags 控制，且預設關閉。
- 對外 API、既有 graph JSON、UI 路由不變。

## Feature Flags（default: false）

- `amon.planner.enabled`：啟用 PlanGraph pipeline 入口。
- `amon.planner.preview_only`：只產生/預覽 PlanGraph，不進入執行。
- `amon.tools.unified_dispatch`：工具派發走統一路徑（保留舊路徑）。

## 回滾策略

- 任何異常直接 fallback 至既有 ExecGraph 直跑流程。
- 維持「flags 全關」可完全回到舊行為。
- 若 rollout 後觀測異常，先關閉 `amon.planner.enabled` 與 `amon.tools.unified_dispatch`。

## 事件觀測（新增類型）

為不影響既有流程，先新增事件型別字串常數：

- `execution_mode_decision`
- `plan_generated`
- `plan_compiled`
- `tool_dispatch`

目前僅提供型別註冊；是否發送由各流程分階段導入。
