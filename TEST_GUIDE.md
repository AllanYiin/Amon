# TEST_GUIDE

## 1) 核心測試矩陣（TaskGraph v3）

```bash
python -m compileall src tests
python -m unittest discover -s tests -p "test_*.py"
python -m unittest \
  tests.test_chat_continuation_guard \
  tests.test_chat_continuation_flow \
  tests.test_ui_chat_stream_init \
  tests.test_chat_session_store
python -m unittest tests.test_ui_graph_frontend_smoke
python -m unittest tests.test_ui_graph_run_adapter
```

## 2) Anti-legacy 檢查

```bash
rg -n "PlanGraph|plan_execute|legacy runtime|GraphRuntime|exec graph|graph\.v2|graph\.legacy|compile_plan_to_exec_graph" src tests docs README.md DEVELOPMENT.md TEST_GUIDE.md SPEC_v1.1.3.md
```

驗收規則：

- 正式執行文件與主流程碼不得把舊術語當主路徑。
- 舊術語僅可出現在 migration/import 或歷史追蹤文件。

## 3) v3 graph fixture / smoke / UI regression

- fixture：`docs/plan.json`（`taskgraph.v3`）
- smoke：`tests.test_ui_graph_frontend_smoke`
- adapter contract：`tests.test_ui_graph_run_adapter`
- 手動 UI 回歸：`docs/ui-regression-graph-context.md`

## 4) 環境限制處理

若環境受限，至少需通過 `python -m compileall src tests`，並在 PR 註明未跑項目與原因。
