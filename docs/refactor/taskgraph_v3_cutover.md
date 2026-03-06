# TaskGraph v3 Cutover Checklist（追蹤用）

> 目的：提供可打勾的 cutover 追蹤清單，避免「宣稱完成但仍有舊路徑」的落差。

## A. 目標終態（Definition of Done）

- [ ] `docs/plan.json` 版本固定為 `taskgraph.v3`。
- [ ] `TaskGraph3Runtime` 成為唯一 production runtime。
- [ ] legacy/v2 僅保留 migrate/import 工具，不再作為主執行路徑。
- [ ] runtime 對不支援 node type 皆 fail-fast，無靜默略過。
- [ ] run artifact 檔名保持相容：`state.json` / `events.jsonl` / `graph.resolved.json`。

## B. 現況已知 legacy 殘留（需逐步清除）

- [ ] `PlanGraph`
- [ ] `compile_plan_to_exec_graph`
- [ ] `taskgraph3.engine_runtime.GraphRuntime`
- [ ] `plan_execute` 命名與測試
- [ ] CLI step5/step6 相容殘留

## C. Phase Gate

### Phase 0（文件校正）
- [x] 重寫 migration 文件，改為「進行中」。
- [x] README / SPEC / DEV / TEST / release checklist 同步加註過渡狀態。
- [x] 建立 anti-legacy 關鍵字清單。

### Phase 1（執行路徑盤點 + fail-fast 防線）
- [ ] 逐一標記主執行路徑中的 legacy 入口。
- [ ] 對不支援 node type 增加 fail-fast 測試。

### Phase 2（runtime 單一路徑）
- [ ] 將 production 執行入口收斂到 `TaskGraph3Runtime`。
- [ ] 移除/封鎖雙軌執行相容層（除明確短期 shim）。

### Phase 3（CLI 與測試命名清理）
- [ ] 清理 step5/step6 舊命名殘留。
- [ ] `plan_execute` 相關命名改為 v3 對應語彙。

### Phase 4（legacy 封存）
- [ ] legacy/v2 僅剩 migrate/import。
- [ ] anti-legacy guard 升級為 CI 阻擋規則。