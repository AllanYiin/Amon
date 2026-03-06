# TaskGraph v3 Migration（進行中，尚未 cutover）

> 本文件描述 **TaskGraph v3 cutover 的現況與遷移計畫**。目前尚未完成全面切換，不得宣稱 migration done。

## 目前狀態（as-is）

目前 repo 仍同時存在 v3 與舊命名/舊路徑，屬於過渡期：

- 舊模型名稱與型別仍可見：`PlanGraph`
- 舊編譯路徑仍可見：`compile_plan_to_exec_graph`
- 舊 runtime 類別仍可見：`taskgraph3.engine_runtime.GraphRuntime`
- `plan_execute` 命名與對應測試仍存在
- CLI step5/step6 還有舊相容殘留

## Cutover 終態（to-be）

以下條件 **全部達成** 才能宣告 TaskGraph v3 migration 完成：

1. `docs/plan.json` 必須是 `version = taskgraph.v3`。
2. `TaskGraph3Runtime` 成為唯一 production runtime。
3. legacy/v2 僅保留在 migrate/import 工具鏈，不可作為執行主路徑。
4. runtime 不得對不支援的 node type 靜默略過，必須明確 fail-fast。
5. run artifact 檔名維持相容：`state.json`、`events.jsonl`、`graph.resolved.json`。

## 分階段遷移清單（追蹤用）

- Phase 0（本階段）：文件校正與遷移清單建立（不改執行邏輯）。
- Phase 1：盤點與標記所有 legacy/v2 執行入口，補 fail-fast 測試。
- Phase 2：收斂 runtime 入口到 `TaskGraph3Runtime`，移除雙軌主執行路徑。
- Phase 3：清理 CLI step5/step6 相容殘留，更新對應測試命名。
- Phase 4：封存 legacy/v2 為 migrate/import-only，完成 anti-legacy guard。

## 驗收與回歸要求

每個 phase 都必須：

- 同步更新測試（至少含 deterministic 回歸）。
- 若有使用者可見變更，更新 README/SPEC/測試指南。
- 在 PR 附上實際執行命令與結果；失敗需註明原因。

可搭配 `docs/refactor/taskgraph_v3_cutover.md` 與 `docs/refactor/taskgraph_v3_forbidden_legacy_refs.md` 做追蹤。