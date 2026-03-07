# Release Checklist（TaskGraph v3 單一路徑）

## 0) Anti-legacy 快速檢查（必跑）

```bash
rg -n "PlanGraph|plan_execute|legacy runtime|GraphRuntime|exec graph|graph\.v2|graph\.legacy|compile_plan_to_exec_graph" src tests docs README.md DEVELOPMENT.md TEST_GUIDE.md SPEC_v1.1.3.md
```

驗收規則：

- 正式文件不得把上述術語當成主路徑。
- 若出現，必須明確標註為「歷史背景」或「匯入/轉換工具」。

## 1) 靜態與單元測試（必跑）

```bash
python -m compileall src tests
python -m unittest discover -s tests -p "test_*.py"
python -m unittest \
  tests.test_chat_continuation_guard \
  tests.test_chat_continuation_flow \
  tests.test_ui_chat_stream_init \
  tests.test_chat_session_store
```

## 2) v3 Graph fixture / smoke

```bash
python -m unittest tests.test_ui_graph_frontend_smoke
python -m unittest tests.test_ui_graph_run_adapter
```

## 3) UI regression（Graph / Chat / Context）

- 依 `docs/ui-regression-graph-context.md` 逐步驗證：
  - Graph node list / Mermaid click / node drawer
  - Chat SSE 更新到 graph node states
  - Context clear 帶 `chat_id` 與統計同步

## 4) 發版結論

PR 必須附：

1. 實際執行命令
2. 成功/失敗結果
3. 若失敗，環境限制與風險摘要
