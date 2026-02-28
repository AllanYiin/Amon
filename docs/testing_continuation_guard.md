# 對話續聊回歸測試指南

## 本地執行（與 CI 同步）

```bash
python -m compileall src tests
python -m unittest \
  tests.test_chat_continuation_guard \
  tests.test_chat_continuation_flow \
  tests.test_ui_chat_stream_init \
  tests.test_chat_session_store \
  tests.test_chat_session_endpoint_behavior
```

> CI workflow：`.github/workflows/chat-continuation-guard.yml`

## 如何新增測試案例

1. **優先 deterministic**：禁止依賴真實模型回覆內容；請使用 patch/stub 固定輸出。
2. **至少覆蓋一個回歸斷點**：
   - chat_id 穩定（不被覆寫/重建）
   - history 有帶入 prompt
   - stream done 後有完整 `type=assistant`
3. **測試命名建議**：
   - 檔名：`tests/test_chat_continuation_*.py`
   - 方法名：`test_<行為>_<預期結果>`
4. **提交前必跑**：執行本頁「本地執行」命令，確保可在離線/受限網路環境穩定重現。

## 新增回歸覆蓋重點

- `tests.test_chat_session_endpoint_behavior`：驗證 `/v1/chat/sessions` 為 ensure semantics（incoming/latest/new）。
- `tests.test_chat_continuation_flow`：模擬 hydrate 後再次 ensure session，確認 chat_id 不被覆寫且第二輪 `history_count >= 2`。
- `tests.test_chat_continuation_guard`：傳入不存在 chat_id 時會 fallback 並寫入 `chat_session_fallback` warning log。
