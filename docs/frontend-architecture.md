# Amon UI 前端架構維護指南（TaskGraph v3）

## 1) 正式執行模型（前端視角）

- UI 單一入口：`src/amon/ui/index.html`（hash route）。
- Graph 資料來源：`/v1/runs/{run_id}/graph`，payload 為 **taskgraph.v3 run bundle**。
- 前端只接受 v3 graph payload，不再把 v2/legacy 當作執行主路徑。

## 2) Graph payload / run bundle 契約

UI 維護時，請以以下欄位作為穩定契約：

- `run_id`、`status`、`updated_at`
- `graph_mermaid`（Mermaid 原始碼）
- `nodes[]`
  - `id`
  - `type`（v3 node type）
  - `title`
  - `status`（pending/running/succeeded/failed/cancelled）
  - `inputs` / `outputs`
- `node_states`（事件流同步狀態，用於覆蓋 list/SVG 標籤）

## 3) v3 Node Type（UI 要求）

- `agent_task`
- `tool_call`
- `write_file`
- `approval`
- `branch`
- `join`

規則：

1. 未支援 node type 必須顯示錯誤狀態，不可靜默吞掉。
2. `type` 顯示字串須與後端回傳一致，不做 legacy alias 回填。

## 4) Mermaid 與狀態同步

- Mermaid 只負責圖形結構；狀態以 `nodes[].status + node_states` 驅動。
- 點擊 `node-list` 與 Mermaid SVG node 必須共用同一路徑（同一個 `selectNode(nodeId)`）。
- 若 `graph_mermaid` 缺失：顯示空狀態與診斷訊息，不做舊格式 fallback。

## 5) 文件分層原則

- **正式執行模型**：本文件、README、SPEC、TEST_GUIDE。
- **匯入/轉換工具**：`docs/migration_v3.md`（僅工具用途）。
- **歷史背景**：`docs/refactor/*`（只讀追蹤，不作新功能依據）。
