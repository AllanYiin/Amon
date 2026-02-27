# Refactor Phases

## Phase 2：UI chat stream 與 timeout 止血驗收

1. planner flag 關閉時，`run_plan_execute_stream` 必須走 single 相容串流路徑，UI 可持續收到 token 或 final。
2. 每次 chat stream 執行都必須在 SSE `token/done` 事件帶上：`project_id`、`chat_id`、`run_id`。
3. `sessions/chat/<chat_id>.jsonl` 的 assistant 事件必須帶 `project_id`、`chat_id`、`run_id`，且最終必有 assistant final。
4. `.amon/runs/<run_id>/events.jsonl` 必須可追溯 `project_id`、`run_id`，並補上 `chat_id` 關聯。
5. timeout 政策採 inactivity 為主：長輸出只要持續有 token/event 進展，不應被 60 秒固定 wall-clock 直接中斷。
6. 若觸發 timeout，優先回傳 warning/done（timeout）並補寫 chat session 的可理解 assistant 摘要，避免 UI 無回覆。
