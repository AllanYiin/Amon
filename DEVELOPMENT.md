# 開發環境快速上手（本機）

## 1) 安裝與初始化

```bash
pip install -e .
amon init
```

## 2) TaskGraph v3 單一路徑開發原則

- 正式執行模型：只允許 `taskgraph.v3`。
- `docs/plan.json` 視為正式 v3 範例與 smoke 基準。
- legacy/v2 僅能存在於 migrate/import 工具，不得回流主執行路徑。

## 3) Anti-legacy 檢查（開發期必跑）

```bash
rg -n "PlanGraph|plan_execute|legacy runtime|GraphRuntime|exec graph|graph\.v2|graph\.legacy|compile_plan_to_exec_graph" src tests docs README.md DEVELOPMENT.md TEST_GUIDE.md SPEC_v1.1.3.md
```

若命中結果屬於正式文件或主流程程式碼，需修正為 v3 語彙；只有 migration/history 區可保留舊術語。

## 4) 必跑檢查

```bash
python -m compileall src tests
python -m unittest discover -s tests -p "test_*.py"
python -m unittest \
  tests.test_chat_continuation_guard \
  tests.test_chat_continuation_flow \
  tests.test_ui_chat_stream_init \
  tests.test_chat_session_store
```

## 5) v3 Graph fixture / smoke / UI regression

```bash
python -m unittest tests.test_ui_graph_frontend_smoke
python -m unittest tests.test_ui_graph_run_adapter
```

手動 UI 回歸依 `docs/ui-regression-graph-context.md` 執行。

## 6) 啟動 UI

```bash
amon ui --port 8000
```
