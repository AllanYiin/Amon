# TaskGraph v3 Anti-legacy 禁止引用清單

下列關鍵字與模組在 cutover 期間列為「禁止新增依賴」：

- `PlanGraph`
- `compile_plan_to_exec_graph`
- `legacy_graph_runtime`
- `taskgraph3.engine_runtime`
- `taskgraph3.migrate`
- `graph migrate`
- `plan_execute`
- CLI step5 / step6 舊相容邏輯

## 檢查命令

```bash
rg -n "PlanGraph|compile_plan_to_exec_graph|legacy_graph_runtime|taskgraph3\.engine_runtime|taskgraph3\.migrate|graph migrate|plan_execute|step5|step6" src tests docs
```

## 說明

- 現況以 TaskGraph v3 為唯一機制，新增 legacy 參考視為回歸。
- 新功能不得再引入任何 legacy shim。
- 本清單已屬 CI 阻擋範圍。
