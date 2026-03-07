# Thread Hard Cutover 設計鎖定與影響盤點

> 目的：本文件只做「設計鎖定（design lock）」與「影響盤點（impact inventory）」，不改動現有執行邏輯。  
> 原則：先修正 active conversation ownership / restore invariant，再做命名切換；不進行全 repo 文字替換。

## 1. 範圍與非範圍

### 1.1 本次範圍（僅規劃）
- 鎖定 hard cutover 目標：最終不保留 `chat_id`、`/v1/chat/*`、chat 命名相容層。
- 鎖定分階段策略與每階段 hot files。
- 鎖定 storage / API / UI state 的目標 schema 與 migration 路徑。
- 鎖定 deterministic 測試改寫順序（不依賴外部網路）。

### 1.2 非範圍（本次不做）
- 不做全 repo rename。
- 不重寫 UI 架構（維持 `index.html + hash routes + bootstrap` 既有架構）。
- 不調整與 thread cutover 無直接關聯的功能與視覺。

---

## 2. 設計鎖定：核心不變量（Invariants）

### 2.1 Ownership invariant（active conversation ownership）
定義：`active_thread_id` 必須可由「當前 active project」唯一擁有與驗證。

- **I1**：任一請求若帶 `thread_id`，後端必須驗證其檔案/記錄存在於該 `project_id` 範圍內；不存在不可跨專案借用。
- **I2**：前端 restore 時，`project_id -> thread_id` 只可在同 project 內回填。
- **I3**：SSE 事件帶回的 `thread_id` 僅在 `event.project_id == active_project_id`（或無專案模式）時可覆寫目前 active thread。

### 2.2 Restore invariant（reload / reconnect）
定義：重新整理、重連、切專案後，active thread 恢復必須 deterministic。

- **R1**：優先級固定：`incoming thread_id` > `project scoped remembered thread_id` > `latest thread` > `new thread`。
- **R2**：若 remembered thread 不存在，必須清除該 mapping 並回退 `latest/new`，不可保留髒資料。
- **R3**：context/history 載入必須與 active thread 同步來源，不得出現 history 與 context 對不同 thread 的 split-brain。

---

## 3. 目標 Schema（Cutover 終態）

> 下列為 **終態 schema**；真正落地依 phase 逐步替換。

### 3.1 Storage schema

#### A) Session event log
- 路徑：`<project>/sessions/threads/<thread_id>.jsonl`
- 單行事件（JSONL）最小欄位：
  - `type`（`user|assistant|router|plan_created|command_result|...`）
  - `text`
  - `project_id`
  - `thread_id`
  - `ts`
  - 選填：`run_id`、`command`、`metadata`

#### B) Parsed message cache
- 路徑：`<project>/.amon/context/thread_messages/<thread_id>.json`
- 結構：
  - `source_mtime_ns`
  - `source_size`
  - `messages: [{role, text, ts}]`

#### C) Attachment inbox（thread scoped）
- 路徑：`<project>/docs/inbox/<thread_id>/...`
- manifest 需含：
  - `thread_id`
  - `project_id`
  - `entries[]`（檔名、MIME、相對路徑、時間）

#### D) Active pointer（可選）
- 路徑：`<project>/.amon/state/active_thread.json`
- 目的：在 server 端提供 deterministic restore 來源（避免僅依 mtime 推斷）
- 結構：`{ "project_id": "...", "thread_id": "...", "updated_at": "..." }`

### 3.2 API schema

#### A) Thread lifecycle
- `POST /v1/threads`
  - req: `{ "project_id": "...", "thread_id": "(optional)" }`
  - resp: `{ "thread_id": "...", "thread_id_source": "incoming|latest|new" }`

#### B) Streaming bootstrap
- `POST /v1/threads/stream/init`
  - req: `{ "project_id": "...", "thread_id": "(optional)", "message": "..." }`
  - resp: `{ "stream_token": "...", "ttl_s": 30 }`

- `GET /v1/threads/stream?...`
  - query: `project_id`, `stream_token`（或 `message`）, `thread_id`（optional）
  - SSE payload 必帶 `project_id` + `thread_id`（若已確定 thread）

#### C) Read models
- `GET /v1/projects/{project_id}/history?thread_id=...`
- `GET /v1/projects/{project_id}/context?thread_id=...`
- `GET /v1/projects/{project_id}/context/stats?thread_id=...`

#### D) Mutations
- `POST /v1/threads/plan/confirm`
  - req: `{ "project_id", "thread_id", "command", "args", "confirmed" }`

- `POST /v1/context/clear`
  - `scope=thread` 時 req 必須帶 `thread_id`

> Hard cutover 終態：移除 `/v1/chat/*`，不保留 alias/fallback。

### 3.3 UI state schema

- 全域 state 關鍵欄位：
  - `projectId: string | null`
  - `threadId: string | null`
  - `projectThreadSessions: Record<projectId, threadId>`

- Restore 流程：
  1. 選定 project。
  2. 讀 `projectThreadSessions[projectId]`。
  3. 呼叫 `POST /v1/threads` 驗證/修正後取得 authoritative `thread_id`。
  4. 將 authoritative `thread_id` 回寫 state + localStorage。

- Event apply 規則：
  - 僅當 `event.project_id` 與 active project 一致時，`event.thread_id` 可更新 `state.threadId`。
  - 切專案時先保存舊 project 的 `threadId`，再切換到新 project 對應記憶值。

---

## 4. Phase 規劃（先 invariant，後命名）

## Phase 0：設計鎖定與盤點（本文件）
- 產出：本文件。
- 不改邏輯。

## Phase 1：修復 ownership / restore invariant（仍保留 chat 命名）
- 目標：先讓「目前 chat flow」具備正確 ownership 與 restore 行為，避免 rename 時放大錯誤。
- 改動界線：
  - 後端 session resolve / history select / context select 的一致性。
  - 前端 `project ↔ active conversation` 映射與事件套用條件。
- 禁止：任何對外命名切換、端點改名。

## Phase 2：命名切換（chat -> thread）
- 目標：對外 API、內部 state、storage 命名切為 thread。
- 做法：依 hot files 分區替換（backend API layer -> domain/service -> UI state -> tests），不做全 repo 一鍵替換。
- 終態：移除 chat endpoint 與 chat_id 命名相容層。

## Phase 3：收斂與清除（legacy 移除）
- 目標：刪除殘留 chat 名稱/路徑/測試 fixture。
- 驗證：anti-legacy 關鍵字檢查 + 全量 deterministic tests。

---

## 5. Hot files 與 Phase scope

### Phase 1 hot files（invariant 修復）

#### Backend
- `src/amon/chat/session_store.py`
- `src/amon/chat/continuation.py`
- `src/amon/ui_server.py`

#### Frontend
- `src/amon/ui/static/js/bootstrap.js`
- `src/amon/ui/static/js/domain/runsService.js`
- `src/amon/ui/static/js/domain/contextService.js`
- `src/amon/ui/static/js/views/chat.js`
- `src/amon/ui/event_stream_client.js`

#### Tests（deterministic）
- `tests/test_chat_session_store.py`
- `tests/test_chat_session_endpoint_behavior.py`
- `tests/test_chat_continuation_guard.py`
- `tests/test_chat_continuation_flow.py`
- `tests/test_ui_chat_stream_init.py`
- `tests/test_ui_async_api.py`（僅 thread ownership/restore 相關案例）

### Phase 2 hot files（命名切換）

#### Backend/API
- `src/amon/ui_server.py`（路由與 request/response schema）
- `src/amon/chat/session_store.py`（`chat_id` -> `thread_id`）
- `src/amon/chat/attachments.py`
- `src/amon/chat/continuation.py`
- `src/amon/commands/executor.py`（plan payload 欄位）

#### Frontend
- `src/amon/ui/static/js/bootstrap.js`
- `src/amon/ui/static/js/domain/runsService.js`
- `src/amon/ui/static/js/domain/contextService.js`
- `src/amon/ui/static/js/views/chat.js`（視圖名稱可後續再議，先改 state/api 欄位）
- `src/amon/ui/event_stream_client.js`

#### Tests
- 先改 contract/endpoint 測試，再改 UI/integration 測試，最後改 anti-legacy。

### Phase 3 hot files（legacy 清除）
- `tests/*chat*` 舊命名測試（重命名與語意更新）
- `docs/*` 中 API 文件與術語收斂
- anti-legacy 規則新增 chat 遺留詞彙檢查

---

## 6. 測試改寫順序（deterministic / offline）

1. **Session ownership 單元測試**
   - 驗證 incoming/latest/new 決議順序。
   - 驗證跨 project thread 不可被接受。

2. **Restore invariant 單元測試**
   - 驗證前端記憶值不存在時會回退且清理 mapping。
   - 驗證 SSE 舊事件不覆寫新 active project。

3. **API contract 測試**
   - `POST /v1/threads`、`/v1/threads/stream/init`、`/v1/threads/plan/confirm`。
   - `context/history/stats` 的 `thread_id` query/response 一致性。

4. **Continuation guard 回歸**
   - 沿用現有 deterministic fixture，替換欄位命名與斷言。

5. **UI stream/init & async API 測試**
   - 驗證 stream token carry 的 `thread_id` 與後續 event apply 一致。

6. **Legacy 防線測試**
   - anti-legacy 檢查禁止新增 `chat_id`/`/v1/chat`。

---

## 7. 風險盤點與緩解

- **RISK-1：專案切換時 thread 被舊 SSE 覆寫**
  - 緩解：event apply 增加 `project_id` 比對 gate；加入回歸測試。

- **RISK-2：history/context 對應到不同 thread（split-brain）**
  - 緩解：統一用同一 authoritative `thread_id` 載入；測試覆蓋。

- **RISK-3：hard cutover 後第三方腳本仍呼叫 `/v1/chat/*`**
  - 緩解：在 cutover PR 與 release note 明確宣告 breaking change。

- **RISK-4：cache 路徑切換造成舊資料失聯**
  - 緩解：phase 2 可做一次性 migration script（純本地 deterministic），phase 3 再移除舊路徑。

---

## 8. Validation baseline（本次設計文件 PR）

- 本次僅文件新增，不變更執行邏輯。
- 測試/檢查仍依 repo 規範執行，以確認無副作用。
