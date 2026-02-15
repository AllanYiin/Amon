# Observability Schema Contract

此文件定義 Amon logs/events 的最小關聯欄位契約，目標是讓重要行為可跨模組追蹤與關聯。

## 必備關聯欄位

以下欄位在重要事件中應存在（可為 `null`，但鍵不可缺漏）：

- `project_id`：專案 ID。無專案情境時使用虛擬值 `__virtual__`。
- `run_id`：graph/runtime 的執行批次 ID。
- `node_id`：graph node ID。
- `event_id`：事件唯一 ID。
- `request_id`：UI task、SSE 或 sandbox runner request 追蹤 ID。
- `tool`：工具呼叫名稱（例如 `filesystem.read`）。

## 模組對應

- `amon.events`（event bus）
  - 透過 `emit_event(...)` 落地到 `~/.amon/events/events.jsonl`。
  - 會補齊關聯欄位，並對 `project_id` 套用虛擬專案 fallback。

- `graph_runtime`
  - `runs/<run_id>/events.jsonl` 的每筆 run/node 事件都包含關聯欄位。
  - 若由 UI 任務觸發，`request_id` 會從 API task 帶入 runtime。

- `tooling.audit`
  - `logs/tool_audit.jsonl` 保留工具稽核資訊，並新增 run/node/event/request 關聯鍵。

- `ui_server`
  - `/v1/chat/stream` 的 SSE payload 會補齊關聯欄位。
  - 未帶 project 時，自動補 `project_id=__virtual__` 以便串接追蹤。

## 相容性原則

- 新欄位以「補齊不破壞」方式加入，不移除既有欄位。
- 既有消費端只讀取既有鍵仍可運作。
- 所有識別欄位禁止寫入敏感資訊（token/key/password/PII）。
