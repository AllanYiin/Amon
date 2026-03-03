# Migration V3（已完成）

## 狀態
- ✅ 已完成：專案已全面收斂為單一路徑 **TaskGraph v3 runtime**。
- ✅ 已移除：legacy runtime 與 v2 runtime 相關程式碼、測試與文件引用。

## 現行使用方式（僅 v3）
- CLI 執行：`amon run "<任務>" --project <project_id> --engine taskgraph3`
- CLI 對話：`amon chat --project <project_id> --engine taskgraph3`
- Graph 執行入口：`AmonCore.run_graph(...)`（只接受 `version = taskgraph.v3`）

## 保護機制
- anti-legacy 檢查以 FAIL 模式阻擋任何 legacy / v2 重新引入。
- 文件掃描同樣檢查已刪除路徑不得再被引用。
