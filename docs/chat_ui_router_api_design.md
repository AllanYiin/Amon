# Vibe Coding 開發規範

以下設計說明以「最小改動、模組化、向下相容」為原則，僅提供插入點與後續階段範圍規劃，不做功能實作。

## 既有結構與主要入口（快速定位）

### CLI 入口（指令註冊點）
- `src/amon/cli.py`：
  - `build_parser()` 為指令註冊點（`amon` CLI 子指令集中定義）。
  - `main()` 為 CLI 主入口，依 `args.command` 分派到 `_handle_*`。 

### Project / Run / Graph 模組位置
- Project 與 Run 核心流程：`src/amon/core.py`
  - 專案生命週期（create/list/show/update/delete/restore）
  - `run_single/run_self_critique/run_team/run_graph/...` 皆集中在 AmonCore。 
- Graph runtime：`src/amon/graph_runtime.py`
  - `GraphRuntime.run()` 負責建立 `graph.resolved.json`、`state.json`、`events.jsonl`。

### UI 入口
- `src/amon/ui_server.py`：簡易 HTTP UI 服務與 API 路由（`/v1/*`）。
- 靜態 UI：`src/amon/ui/` 下的 HTML/CSS。

## logs / sessions / runs 落地位置
- 全域 logs：`~/.amon/logs`（或 `AMON_HOME/logs`）。
  - 由 `src/amon/logging.py::_log_path()` 與 `AmonCore.logs_dir` 決定。
- 專案 sessions：`<project_path>/sessions/*.jsonl`。
  - `AmonCore._create_project_structure()` 建立 `sessions/`。
- graph runs：`<project_path>/.amon/runs/<run_id>/`。
  - `GraphRuntime.run()` 產出 `graph.resolved.json`、`state.json`、`events.jsonl`。

## 新增模組建議位置（不實作，僅插入點）

### 1) `amon/chat/`（Chat session + router）
- 建議目錄：`src/amon/chat/`
- 建議檔案：
  - `src/amon/chat/__init__.py`
  - `src/amon/chat/session.py`（Chat session lifecycle，讀寫 sessions/）
  - `src/amon/chat/router.py`（Chat UI/CLI/API routing，對應 Graph runtime）
- 插入點：
  - `AmonCore` 增加 chat session 入口（例如 `core.start_chat_session()`）。
  - `ui_server.py` 新增 `/v1/chat/*` API 路由（僅註冊，不改既有 endpoints）。

### 2) `amon/commands/`（API command registry + executor）
- 建議目錄：`src/amon/commands/`
- 建議檔案：
  - `src/amon/commands/__init__.py`
  - `src/amon/commands/registry.py`（command 註冊、元資料、ACL）
  - `src/amon/commands/executor.py`（對接 AmonCore + graph runtime）
- 插入點：
  - CLI 指令新增一個 `commands` 子指令（註冊/列出/執行）。
  - UI API 新增 `/v1/commands/*`（與 CLI 行為一致）。

### 3) `amon/ui/`（Chat UI）
- 既有 `src/amon/ui/` 是靜態 HTML。
- 若要新增 Chat UI：
  - 建議新增 `src/amon/ui/chat.html` 與 `chat.css`（或延伸既有 `styles.css`）。
  - `ui_server.py` 僅新增路由或靜態檔引用，維持原有 UI。 
- 若需 CLI TUI（備案）：可新增 `src/amon/ui_tui.py`，並由 `cli.py` 新增 `amon ui --mode=tui`。

## 檔案清單 + Phase 1~N 改動範圍

### 新增（建議）
- `src/amon/chat/__init__.py`
- `src/amon/chat/session.py`
- `src/amon/chat/router.py`
- `src/amon/commands/__init__.py`
- `src/amon/commands/registry.py`
- `src/amon/commands/executor.py`
- `src/amon/ui/chat.html`（或 `src/amon/ui/chat/` 資料夾）
- `src/amon/ui/chat.css`（或整合至 `styles.css`）
- （如需要）`src/amon/ui_tui.py`

### Phase 1（最小插入點）
- 建立 `amon/chat/`、`amon/commands/` 目錄與空檔案。
- `cli.py` 新增最小指令入口（例如 `amon chat`、`amon commands`），僅打印提示或回傳 501（未實作）。
- `ui_server.py` 新增 `/v1/chat/health` 或 `/v1/commands/health`，確認路由可達。

### Phase 2（Graph-first 串接）
- `Chat Router -> GraphRuntime`：
  - 每次 chat 指令都落地到 `.amon/runs/<run_id>/`，確保 `graph.resolved.json + state.json + events.jsonl` 產生。
- `Session` 落地到 `sessions/`：
  - Chat 每次互動寫入 `sessions/<session_id>.jsonl`。

### Phase 3（Chat UI + API）
- `ui/chat.html` 與 `/v1/chat/*` API 對接。
- API commands registry + executor 完整串接（CLI + UI 共用）。

### Phase 4（擴充功能）
- Chat 任務模板化（graph template）
- Chat UI 支援 session 瀏覽、進度條、錯誤 toast、檔案預覽

## 最後結論：建議的目錄/檔案
- `src/amon/chat/`（session/router）
- `src/amon/commands/`（registry/executor）
- `src/amon/ui/chat.html`（或 `src/amon/ui/chat/`）
- （備案）`src/amon/ui_tui.py`

## 盡量少改的現有檔案
- `src/amon/cli.py`（新增 `chat`、`commands` 子指令）
- `src/amon/ui_server.py`（新增 `/v1/chat/*`、`/v1/commands/*` 路由）
- `src/amon/core.py`（新增 chat session API，但不動既有流程）

