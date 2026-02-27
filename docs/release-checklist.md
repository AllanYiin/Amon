# Release Checklist（5–10 分鐘 Smoke + Contract）

每次改動前請先啟動 UI，再依序執行下列人工驗收，避免出現「console 有、UI 沒」或功能退化。

## 0) 一鍵檢查指令

```bash
python -m compileall src tests
python -m unittest discover -s tests -p "test_*.py"
python -m unittest \
  tests.test_chat_continuation_guard \
  tests.test_chat_continuation_flow \
  tests.test_ui_chat_stream_init \
  tests.test_chat_session_store
pytest
```

## 1) 啟動 UI

```bash
amon ui --port 8000
```

打開 `http://127.0.0.1:8000`，以下步驟都在同一個專案完成。

## 2) 對話與 Planner 路徑

1. 建立新專案。
2. 在 Chat 輸入一段任務（例如「幫我建立一個簡單 landing page」）並送出。
3. 確認畫面可看到 planner/graph 相關流程節點或事件（非空白、非只在 console）。

## 3) Logs 與專案作用域

1. 完成至少一次對話後，確認專案資料夾存在 `.amon/logs/`。
2. 確認至少出現：
   - `.amon/logs/events.log`
   - `.amon/logs/billing.log`
3. 檔案內容需包含對應 `project_id`。

## 4) Context Stats 驗收

1. 開啟 UI 的 Context/上下文統計區塊。
2. 確認 `token_estimate` 有數值：
   - `used`
   - `capacity`
   - `remaining`
   - `estimated_cost_usd`
3. 確認分類列表 `categories` 非空，且每個分類至少有 `key`、`tokens`。

## 5) Billing Summary 驗收

1. 開啟 UI 的 Billing/成本頁。
2. 確認 summary 與趨勢圖有數值，不是全 0 或空陣列。
3. 確認至少可見 UI 依賴欄位（例如 `project_total`、`mode_breakdown`、`run_trend`）。

## 6) Workspace 預覽 iframe 驗收

1. 在專案工作區建立 `workspace/index.html`（可用簡單按鈕與文字）。
2. 回到 UI 右側預覽 iframe。
3. 確認頁面有載入且可互動（例如按鈕可點擊、DOM 有變化）。

## 7) 回歸結論

- 以上任一步驟失敗即不得合併。
- 若環境受限（例如缺少瀏覽器），需在 PR 說明明確註記限制與替代驗證方式。
