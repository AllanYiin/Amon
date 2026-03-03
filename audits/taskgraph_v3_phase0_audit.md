# Vibe Coding 開發規範

> 本次交付聚焦 **PHASE 0（Repo 現況盤點與影響面建模）**，未實作 V3 runner/validator 實際程式碼，先完成替換點清單、相容層草圖與風險評估。

## A) 影響面清單（按模組分組）

### 1) Schema / Serialize / Validator（TaskgraphV2）
- `src/amon/taskgraph2/schema.py`
  - `TaskGraph` / `TaskNode` / `TaskEdge` dataclass 定義。
  - `validate_task_graph()`：檢查 `schema_version == "2.0"`、node/edge 合法性、DAG 無循環。
- `src/amon/taskgraph2/serialize.py`
  - `loads_task_graph()`：從 JSON（含 code fence）轉 `TaskGraph`。
  - `dumps_task_graph()`：輸出穩定序列化格式，edges 用 `from/to`。
- `src/amon/taskgraph2/planner_llm.py`
  - `_taskgraph2_schema_definition()`：內建 TaskGraph2 schema 結構描述，作為 planner 指引。

### 2) Runner / 執行狀態儲存
- `src/amon/taskgraph2/runtime.py`
  - `TaskGraphRuntime.run()`：V2 DAG runtime 主流程。
  - state 寫入 `<project>/.amon/runs/<run_id>/state.json`、events 寫 `events.jsonl`、resolved graph 寫 `graph.resolved.json`。
  - `_build_graph()`：建立 adjacency/incoming 供拓撲執行。
- `src/amon/graph_runtime.py`
  - `GraphRuntime.run()`：legacy graph runtime（以 `nodes[].type` 為主的舊格式）。
  - 同樣落地 run state/events/resolved graph。

### 3) Core / Loader / 格式判斷入口
- `src/amon/core.py`
  - `run_graph()`：讀 graph JSON，若 `schema_version == "2.0"` 且不是 legacy node type，走 `TaskGraphRuntime`；否則走 `GraphRuntime`。
  - `create_graph_template()` / `parametrize_graph_template()` / `run_graph_template()`：template 管線，含 schema_version 分支。

### 4) CLI / Command Executor / Schedules 相容層
- `src/amon/cli.py`
  - `amon graph run` / `amon graph template create` / `amon graph template parametrize` 參數定義。
- `src/amon/commands/executor.py`
  - `_handle_graph_run()`：處理 graph_path/template_id 二選一，呼叫 `core.run_graph` 或 `core.run_graph_template`。
  - `_handle_graph_template_create()` / `_handle_graph_template_parametrize()`。
  - `_handle_schedule_add()` 以 action `graph.run` 建立排程。
- `src/amon/hooks/runner.py`
  - hook action `graph.run` 執行入口與 default runner。

### 5) UI Mermaid / Graph 顯示
- `src/amon/ui_server.py`
  - `_graph_to_mermaid()`：將 graph JSON（nodes/edges）轉 Mermaid 字串。
  - 目前 edges 主要採 `from|from_node -> to|to_node`，尚無 DATA/CONTROL edge style 區分。

### 6) Tests / Fixtures / Docs
- Taskgraph2 單元測試：
  - `tests/test_taskgraph2_schema.py`
  - `tests/test_taskgraph2_runtime_basic.py`
  - `tests/test_taskgraph2_retry_and_validation.py`
  - `tests/test_taskgraph2_tool_loop.py`
  - `tests/test_taskgraph2_output_extraction.py`
  - `tests/test_taskgraph2_planner2.py`
- CLI 與 graph 相容測試：
  - `tests/test_cli_taskgraph2_engine.py`
  - `tests/test_graph_runtime.py`
- Mermaid smoke：
  - `tests/test_ui_graph_frontend_smoke.py`
- 範例：
  - `examples/quickstart_project/graph.json`（legacy graph；非 schema_version 2.0）

---

## 目前 V2 Graph JSON 欄位與語意（收斂）

### TaskGraph2（`schema_version: "2.0"`）
- 頂層欄位：
  - `schema_version`：固定 `2.0`
  - `objective`：任務目標
  - `session_defaults`：初始變數
  - `nodes[]`：節點定義
  - `edges[]`：DAG 邊（`from/to/when?`）
  - `metadata?`：額外資訊
- `nodes[]` 常見欄位：
  - `id/title/kind/description/role`
  - `reads[]` / `writes{}`（上下文讀寫 key）
  - `llm{}`、`tools[]`、`steps[]`
  - `output{type,extract,schema}`
  - `guardrails{allow_interrupt,require_human_approval,boundaries}`
  - `retry{max_attempts,backoff_s,jitter_s}`
  - `timeout{inactivity_s,hard_s}`

### Legacy Graph（非 2.0）
- 頂層多為：`nodes[]`、`edges[]`、`variables{}`
- node 偏向執行型態：`type=write_file|agent_task|sandbox_run...`
- `prompt` 多存在於 `agent_task` node。

---

## 依賴圖（現況）

### 1) CLI graph run
`amon cli graph run` → `commands.executor._handle_graph_run` → `core.run_graph`
→ (A) `TaskGraphRuntime.run`（schema_version=2.0）
→ (B) `GraphRuntime.run`（legacy）
→ run artifacts/state/events (`.amon/runs/<run_id>/...`)
→ UI 讀取 run bundle + `_graph_to_mermaid` render。

### 2) Template path
`amon graph template create/parametrize` → `commands.executor` → `core.create/parametrize_graph_template`
→ `run_graph_template`（依 payload.schema_version 分流）
→ `run_graph`。

### 3) Schedule path
`schedule.add` action=`graph.run` → `hooks.runner` / `commands.executor` → graph runner
→ 最終仍匯入 `core.run_graph` / `run_graph_template`。

---

## B) V2 -> V3 欄位對照表（粗略可落地版本）

| V2 欄位 | 建議 V3 欄位 | 遷移策略 |
|---|---|---|
| `schema_version: "2.0"` | `schemaVersion: "taskgraph.v3"` | 固定改寫，保留原值於 migration warnings |
| `objective` | `globals.objective` 或 `graph.objective` | 直接搬移 |
| `session_defaults` | `globals.variables` / `context.defaults` | 直接搬移 |
| `nodes[].id` | `nodes[].id` | 直接搬移 |
| `nodes[].title` | `nodes[].label`（或 title 保留） | 兼容保留 title，renderer 用 label/title fallback |
| `nodes[].kind` | `nodes[].type`（TASK/GROUP/GATE/ROUTE/ARTIFACT） | 建立 mapping（task→TASK、decision→GATE...） |
| `nodes[].description` | `nodes[].objective` | 直接搬移 |
| `nodes[].reads/writes` | `inputPorts/outputPorts` + `dataBindings` | 產生預設 port（如 `default_in/default_out`） |
| `nodes[].llm/tools/steps` | `skillBindings[]` + intrinsic pipeline | 組裝成 TASK 執行規格 |
| `nodes[].output` | `outputContract` + `extract.output.ports` + `validate.output.schema` | extract/schema 規則拆分 |
| `nodes[].guardrails` | `guardrails[]`（node-level，可選） | 等價映射，補 action（WARN/BLOCK/RETRY）預設 |
| `nodes[].retry/timeout` | `policy.retry` / `policy.timeout` | 直接搬移並套 defaultPolicy precedence |
| `edges[].from/to/when` | `edges[].source/target/type`（CONTROL/DATA） | 先預設 CONTROL；`when` 轉 gate 條件 |
| `metadata` | `metadata` | 原樣保留 |

---

## C) 風險點清單（相容性/資料遷移/測試斷裂）

1. **雙 runtime 分流風險**：目前 `core.run_graph` 同時支持 TaskGraph2 + legacy graph；若全面換 V3，需明確 auto-detect 順序與 fallback，避免誤判。
2. **Template schema_version 分支風險**：`run_graph_template` 目前僅分 `2.0` 與 legacy，新增 V3 後需三分支（legacy/v2/v3）且保留 `graph.run` 介面不變。
3. **Mermaid 渲染語義不足**：現行 `_graph_to_mermaid` 不區分 DATA/CONTROL，V3 若直接導入新邊型，UI 可能「可渲染但語意錯」。
4. **RunState 結構擴充衝擊**：現有 state.json 節點欄位較精簡；V3 需要 `raw_output/ports/metrics/score/violations`，UI API 與 smoke test 需同步。
5. **測試覆蓋偏 V2**：`tests/test_taskgraph2_*` 量大，V3 導入若未提供 migrate-on-read，會大量斷測。
6. **Scheduler/hook action 相容**：`graph.run` 名稱不能改；若 payload 驗證更嚴，舊排程資料要有自動轉換或明確警告。
7. **內建能力與安全邊界**：V3 要求 intrinsic（schema validate/ports extract/metrics/logs/safety/spec schemaize）若先以 mock 落地，需標註 capability 等級避免誤解「已完整接真實技能」。

---

## 相容層設計草圖（建議）

1. `GraphFormatDetector`（auto）
   - `taskgraph.v3` → V3 parser/validator/runner
   - `2.0` → V2 parser，再走 converter（可配置直跑 V2 或轉 V3）
   - 其餘 → legacy parser（可警告 deprecation）

2. `MigrationAdapter`
   - `v2_to_v3(graph) -> (graph_v3, warnings[])`
   - `legacy_to_v3(graph) -> (graph_v3, warnings[])`
   - warning 必須可追蹤（寫 run events + stderr）

3. `UnifiedGraphRunner`
   - CLI/schedule/hook 全部只呼叫 unified runner，內部 auto-detect + compile + execute
   - 保留 CLI 指令名稱：`amon graph run`、action=`graph.run`

4. `MermaidRendererV3`
   - 支援 node type badge + edge style（CONTROL vs DATA）
   - 舊 renderer 保留 fallback，直到 V2 移除。


---

## 附錄：關鍵檔案與函式/類別索引（含行號）

- `src/amon/core.py`
  - `run_graph`（約 L1619）
  - `run_taskgraph2`（約 L1665 / L1702）
  - `create_graph_template`（約 L1765）
  - `parametrize_graph_template`（約 L1801）
  - `run_graph_template`（約 L1824）
- `src/amon/commands/executor.py`
  - `_handle_graph_run`（約 L306）
  - `_handle_graph_template_create`（約 L348）
  - `_handle_graph_template_parametrize`（約 L366）
  - `_handle_schedule_add`（約 L419）
- `src/amon/cli.py`
  - `build_parser` 內 graph 命令參數（約 L200-L217）
- `src/amon/hooks/runner.py`
  - `_default_graph_runner`（約 L73）
  - `_run_graph`（約 L376）
- `src/amon/taskgraph2/schema.py`
  - `TaskGraph` dataclass（約 L81）
  - `validate_task_graph`（約 L89）
- `src/amon/taskgraph2/serialize.py`
  - `dumps_task_graph`（約 L23）
  - `loads_task_graph`（約 L36）
- `src/amon/taskgraph2/runtime.py`
  - `TaskGraphRuntime`（約 L40）
  - `TaskGraphRuntime.run`（約 L60）
- `src/amon/taskgraph2/node_executor.py`
  - `NodeExecutor.execute_llm_node`（約 L41）
  - `extract_output`（約 L111）
  - `validate_output`（約 L139）
- `src/amon/ui_server.py`
  - `_graph_to_mermaid`（約 L3384）

## 附錄：V2/相關 Graph JSON 範例（3 份）

1. `tests/test_cli_taskgraph2_engine.py`（`schema_version: 2.0` 最小整合）
2. `tests/test_taskgraph2_schema.py`（含完整 node output/guardrails/retry/timeout）
3. `examples/quickstart_project/graph.json`（legacy graph：`type/prompt/output_path`）

