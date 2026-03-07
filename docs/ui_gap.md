# UI Gap 收斂結論（TaskGraph v3 單一路徑）

## 1) 目的

本文件只保留「目前仍需補齊」的 UI 差距，並以 v3 為唯一執行模型。

## 2) 已收斂項目

- Graph 主資料來源統一為 v3 run bundle。
- Mermaid 視覺化與 node drawer 行為採同一 `selectNode(nodeId)` 流程。
- Chat 與 Graph 狀態同步以 `run.update/node.update` 事件驅動。

## 3) 仍需追蹤的 gap

1. 高頻事件下的 Graph 局部刷新效能（避免不必要整圖 re-render）。
2. node 狀態標記與 A11y 標示一致性（含鍵盤焦點）。
3. run 空態與錯誤態文案一致性（Graph/Chat/Context）。

## 4) Anti-legacy 約束

- 新 UI 功能不得引入 `graph.v2` / `graph.legacy` 主路徑 fallback。
- 舊術語若需提及，僅能放在 migration/history 文件，不進正式 UI 行為說明。

## 5) 驗收命令

```bash
python -m unittest tests.test_ui_graph_frontend_smoke
python -m unittest tests.test_ui_graph_run_adapter
```
