# TaskGraph v3 Anti-legacy 禁止引用清單

下列關鍵字與模組在 cutover 期間列為「禁止新增依賴」：

- `PlanGraph`
- `compile_plan_to_exec_graph`
- `taskgraph3.engine_runtime.GraphRuntime`
- `plan_execute`
- CLI step5 / step6 舊相容邏輯

## 檢查命令

```bash
rg -n "PlanGraph|compile_plan_to_exec_graph|taskgraph3\.engine_runtime\.GraphRuntime|plan_execute|step5|step6" src tests docs
```

## 說明

- 現有殘留屬於技術債盤點對象，不等同允許新增。
- 新功能若必須暫時相容，需在 PR 明確註記為「短期 shim」與移除時程。
- cutover 完成後，本清單應轉為 CI 強制阻擋。