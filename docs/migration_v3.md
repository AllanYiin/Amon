# TaskGraph v3 Migration（已完成）

> 狀態：**Done**。本 repo 已進入 TaskGraph v3 單一路徑執行模型。

## 1) 正式執行模型（Production Path）

- 正式 graph 規格固定為 `taskgraph.v3`。
- `docs/plan.json` 即為正式範例與基準檔。
- 執行主路徑僅允許 v3 runtime（run artifacts 固定為 `state.json`、`events.jsonl`、`graph.resolved.json`）。
- runtime 對不支援 node type 採 fail-fast，不允許靜默略過。

## 2) 已移除的舊主路徑

以下舊語彙/舊主路徑不得再作為 production execution path：

- `PlanGraph`（作為執行主模型）
- `compile_plan_to_exec_graph`（作為主編譯入口）
- `plan_execute`（作為主模式命名）
- `GraphRuntime`（舊 runtime 命名作為主路徑）
- `graph.v2` / `graph.legacy`（作為主執行格式）

## 3) 保留能力（僅匯入/轉換工具）

下列能力保留，但**僅限 migrate/import 用途**：

- `amon graph migrate --source legacy ... --output ...`（`graph.legacy` -> `taskgraph.v3`）
- `amon graph migrate --source v2 ... --output ...`（`graph.v2` -> `taskgraph.v3`）

規則：

1. 匯入完成後一律以 v3 檔案執行。
2. 禁止在新功能中新增 legacy/v2 執行入口。
3. 舊術語只允許出現在「歷史背景」或「遷移工具」說明區。

## 4) 歷史背景（只讀）

- 本 repo 曾經歷多階段 cutover，早期文件與測試可能提及舊術語。
- 目前維護原則為：
  - 正式路徑文件（README/SPEC/TEST_GUIDE/DEVELOPMENT）僅描述 v3。
  - 舊術語集中於歷史或 refactor 追蹤文件，不得混入正式執行指南。
