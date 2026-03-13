# TaskGraph v3 Anti-legacy 禁止引用清單

下列類型的舊概念在 cutover 後列為「禁止新增依賴」：

- 舊 planning graph 型別與編譯入口
- 舊 runtime 模組與舊 graph 轉換入口
- 舊 planner mode 命名
- CLI step5 / step6 舊相容邏輯

## 檢查命令

```bash
scripts/anti_legacy_graph.sh
```

## 說明

- 現況以 TaskGraph v3 為唯一機制，新增 legacy 參考視為回歸。
- 新功能不得再引入任何 legacy shim。
- 本清單已屬 CI 阻擋範圍。
