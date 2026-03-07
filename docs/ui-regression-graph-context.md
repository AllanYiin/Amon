# UI Regression：Graph / Chat / Context（TaskGraph v3）

## 1) 正式驗收範圍

- Graph page（`#/graph`）
- Chat page + 右側 graph/inspector
- Context page（`#/context`）

目標：確認 UI 全面對齊 v3 單一路徑，不依賴 legacy graph 表現。

## 2) Graph 回歸步驟

1. 進入 `#/graph`，選取 run。
2. 檢查 `graph-code` 與 `graph-preview` 同步。
3. 點 node list 任一節點，確認 drawer 開啟。
4. 點 Mermaid SVG 同一節點，確認走同一路徑並高亮。
5. 驗證 status 來源為 `nodes + node_states`，非舊欄位 fallback。

## 3) Chat ↔ Graph 同步步驟

1. 在 Chat 觸發一次 run。
2. 觀察 `run.update` / `node.update` 事件。
3. 切換到 `#/graph`，確認同一 run 的 node 狀態已更新。
4. run 結束後狀態應停在終態，不應回退 pending。

## 4) Context 回歸步驟

1. 進入 `#/context`，確認統計正常載入。
2. 觸發 clear（chat scope）。
3. 檢查 request 帶 `chat_id`，且清除後統計與列表同步。

## 5) Smoke 建議矩陣

```bash
python -m unittest tests.test_ui_graph_frontend_smoke
python -m unittest tests.test_ui_graph_run_adapter
python -m unittest tests.test_ui_chat_stream_init
python -m unittest tests.test_chat_session_store
```

## 6) 文件分層規則

- 正式執行模型：此文件 + README + TEST_GUIDE。
- 匯入/轉換工具：`docs/migration_v3.md`。
- 歷史背景：`docs/refactor/*`。
