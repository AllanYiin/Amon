# 對話未帶入上文：根因分析與最小修補策略

## 問題摘要
使用者回報「第二輪對話沒有延續第一輪上文」。
本次先不大改架構，以最小可觀測性（程式路徑 + session 行為）定位斷點。

## 涉及檔案與關鍵函式
- `src/amon/ui/static/js/bootstrap.js`
  - `hydrateSelectedProject()`：切換/載入專案時會呼叫 `ensureChatSession()`。
  - `ensureChatSession()`：呼叫 `POST /v1/chat/sessions` 後，直接覆寫 `state.chatId`。
- `src/amon/ui_server.py`
  - `POST /v1/chat/sessions`：每次都 `create_chat_session(project_id)`，不重用現有 chat。
  - `_handle_chat_stream()`：若 query 沒帶 `chat_id`（或被覆寫成新 chat），會以新 chat 跑，歷史為空。
- `src/amon/chat/session_store.py`
  - `load_recent_dialogue()`：僅讀 `type in {user, assistant}` 作為上文。
  - `load_latest_run_context()`：僅從 `assistant` 事件抓最後回覆與 run_id。

## 資料流圖（文字）
1. UI 載入專案 -> `hydrateSelectedProject()`。
2. 先 `loadProjectHistory()` 取得舊 `chat_id`（可延續）。
3. 接著 `ensureChatSession()` 呼叫 `POST /v1/chat/sessions`。
4. 後端每次都新建 chat -> UI 將 `state.chatId` 覆寫成新值。
5. 下一次送訊息時，`/v1/chat/stream` 帶的是新 `chat_id`。
6. `_handle_chat_stream()` 用新 chat 讀歷史，`history=[]`，`prompt_with_history` 實質無上文。

## 你要求的特別檢查

### 1) chat_id 是否每輪重建
- **結論：高機率被重建（至少在每次 hydrate/project 切換時）**。
- 證據：前端 `hydrateSelectedProject()` 固定呼叫 `ensureChatSession()`；`ensureChatSession()` 又呼叫後端建立新 chat。後端 endpoint 也確實每次 `create_chat_session()`。 

### 2) session_store 是否只收 user/assistant
- **結論：不是只收，會收多種 type（router/assistant_chunk/error...）**，但「讀上文」時只取 `user/assistant`。
- 證據：`append_event()` 接受一般事件；`load_recent_dialogue()` 明確只篩 `user/assistant`。

### 3) 是否只寫 assistant_chunk 沒寫 assistant
- **結論：不是。串流中會寫 `assistant_chunk`，流程結束後仍會寫完整 `assistant`。**
- 證據：`_handle_chat_stream()` 在 token 流中 append `assistant_chunk`，結束後 append `assistant` payload。

### 4) prompt 是否真的含歷史
- **結論：程式設計上會帶歷史；問題在 chat_id 被換新時歷史讀不到。**
- 證據：`prompt_with_history = build_prompt_with_history(message, history)`，且 `run_single_stream(... conversation_history=history)`；但 history 來源是 `load_recent_dialogue(project_id, chat_id)`，chat_id 若新建則為空。

## 根因（Root Cause）
主要斷點在「前端 hydrate 階段把可延續的 `chat_id` 覆寫成新 session」，導致下一輪請求帶錯 chat_id，最終讓後端讀不到歷史，呈現「未帶入上文」。

## 最小修補策略（不大改架構）

### 修補點 A（首選，最小風險）
- 檔案：`src/amon/ui/static/js/bootstrap.js`
- 函式：`ensureChatSession()`
- 變更：
  - 若 `state.chatId` 已存在且非空，直接 return，不再呼叫 `POST /v1/chat/sessions`。
  - 只在「沒有 chatId」時才建立新 session。

### 修補點 B（防呆）
- 檔案：`src/amon/ui/static/js/bootstrap.js`
- 函式：`hydrateSelectedProject()`
- 變更：
  - 保留 `loadProjectHistory()` 回傳/設定的 chatId。
  - `ensureChatSession()` 改成「確保存在」而不是「一律新建」。

### 修補點 C（可觀測性，建議同 PR 一起）
- 檔案：`src/amon/ui_server.py`
- 函式：`_handle_chat_stream()`
- 新增 INFO log：
  - `chat_id_source`（client_provided / created_new）
  - `history_count`
  - `has_last_assistant_text`
- 用途：後續可快速驗證「是否又拿到空 history」。

## 可重現測試腳本（手動）

```bash
# 1) 啟動 UI
amon ui --port 8000

# 2) 開啟頁面後選定同一專案，送出第一句，記下 done 的 chat_id（DevTools Network 可看 /v1/chat/stream query）
# 3) 重新整理頁面或切換專案再切回來，再送第二句
# 4) 觀察第二句 /v1/chat/stream 的 chat_id 是否與第一句不同
#    - 若不同，且回覆失去上文，即可重現問題
```

## 可轉自動化測試案例（下一階段）
- 測試名稱建議：`test_ui_hydrate_does_not_overwrite_existing_chat_id`
- 斷言：
  1. `loadProjectHistory()` 先提供既有 `chat_id=chat-old`。
  2. 執行 `hydrateSelectedProject()` 後，`state.chatId` 仍為 `chat-old`。
  3. 送出第二則訊息時，stream query 應帶 `chat_id=chat-old`（非新 ID）。
