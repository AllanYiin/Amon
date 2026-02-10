# Codex 工作契約（Repo Root）

## 1) 依賴/測試/品質工具偵測摘要
- 依賴管理：`pyproject.toml`（setuptools）與 `requirements.txt`（PyYAML）。
- 測試框架：`unittest`（以 `python -m unittest discover -s tests` 執行）。
- Lint/Format：未看到 ruff/black/isort/flake8/mypy 設定；採用最小品質門檻（`compileall`）。

## 2) 必跑命令（CI/本地一致）
> 若命令失敗，需在 PR 說明中標註原因與輸出摘要。

### Lint / 最小品質門檻
```bash
python -m compileall src tests
```

### Tests
```bash
python -m unittest discover -s tests
```

> 若無法完整執行測試，至少保留 `compileall` 作為 smoke check。

## 3) PR 規範
請在 PR 描述中固定提供下列區塊：

### Summary
- 條列本次變更重點（最多 3 點）。

### Risk
- 變更風險說明（例如：低/中/高 + 影響範圍）。

### Validation
- 列出實際執行過的命令與結果（包含失敗或受限原因）。

範例：
```
Summary
- 新增 AGENTS.md 與 DEVELOPMENT.md

Risk
- Low（僅文件與規範）

Validation
- python -m compileall src tests
- python -m unittest discover -s tests (失敗：外部連線 403)
```

## 4) 安全規範（必遵守）
- 嚴禁將 API Key、Token、密碼等 secrets 提交到 repo。
- 禁止在紀錄/範例中包含敏感 payload（PII、憑證、內部 URL）。
- 避免使用隱藏 Unicode 或 bidi 控制字元（如有需要，請明示原因）。
- 所有金鑰應只放在環境變數（例如 `OPENAI_API_KEY`）。

## 5) UI 專案開發指南（Amon UI）

### 5.1 啟動（dev）/測試（test）/建置（build）/lint-format 指令
Amon UI 目前為 `src/amon/ui/` 下的靜態 HTML/CSS，由 Python 內建 HTTP server (`amon ui`) 提供，不使用 Node bundler。

- dev（本機開發與預覽）
  ```bash
  amon ui --port 8000
  ```
  開啟 `http://localhost:8000`。

- test（後端與 UI API 共同 smoke test）
  ```bash
  python -m unittest discover -s tests
  ```

- build（封裝）
  ```bash
  pip install -e .
  ```
  目前無獨立前端打包步驟；UI 以 package data 形式隨 Python 套件安裝。

- lint / format（最小品質門檻）
  ```bash
  python -m compileall src tests
  ```
  目前 repo 尚未配置專用 formatter（black/ruff/prettier）；若新增，請在此區更新。

### 5.2 UI 目錄結構（pages/routes/components/state/api）
目前 UI 採「單檔頁面 + 原生 JS」模式，對應如下：

- pages
  - `src/amon/ui/index.html`：主 Chat UI（含 Context / Graph / Docs 右側分頁）
  - `src/amon/ui/project.html`：專案工作台展示頁
  - `src/amon/ui/single.html`：單一模式展示頁

- routes（由 `src/amon/ui_server.py` 註冊）
  - 頁面：`/`（靜態資源）
  - API：`/v1/*`（projects/chat/runs/jobs/tools/hooks/schedules 等）

- components
  - 目前未拆成前端框架元件，使用語意化區塊與 class 命名（如 `chat-panel`、`context-panel`、`plan-card`、`chat-bubble`）。

- state
  - 前端頁面狀態集中在 `index.html` 的 `state` 物件（`chatId/projectId/plan/streaming/attachments`）。
  - 對話長期狀態由 `amon.chat.session_store` 管理（session/event 落盤）。

- api
  - UI 透過 `fetch('/v1/...')` + `EventSource('/v1/chat/stream?...')` 與 `ui_server` 互動。
  - API 回應採 JSON；串流採 SSE（見 5.4）。

### 5.3 Amon UI 核心規格摘要
- Chat
  - 支援自然語言輸入、附件摘要送出、token streaming、Plan Card 確認流程。

- Context
  - 依專案同步右側資訊（專案概覽、已同步資料狀態）。

- Graph
  - 顯示 Mermaid graph preview 與 graph code；資料來源為最近一次 run 的 `graph.resolved.json`（或 fallback graph）。

- Tools & Skills
  - 目前後端已有 tools 執行 API（例如 `/v1/tools/run`）與 skills 生態（CLI/文件層）；UI 尚未有獨立 Tools/Skills 視覺管理頁，新增時需沿用既有 `/v1/*` 能力與安全約束。

- Config
  - 設定由後端 config 系統管理（global/project precedence）；UI 目前未提供專屬 Config 編輯頁。

- Logs & Events
  - 錯誤與事件由後端寫入 log，chat 流程中的事件另寫入 chat session store；UI 以 toast 與 timeline 顯示關鍵結果。

- Docs
  - Context 右側提供 Docs 清單，來源為專案 `docs/` 目錄檔案索引。

- Bill
  - 規格層要求 billing log（`logs/billing.log`）；目前 UI 尚未實作 billing dashboard，新增時需避免暴露敏感資訊。

### 5.4 事件串流來源與資料格式
- 串流來源
  - 已實作：SSE（Server-Sent Events）
    - Endpoint：`GET /v1/chat/stream?project_id=<id>&chat_id=<id>&message=<text>`
    - Response header：`Content-Type: text/event-stream; charset=utf-8`
  - 未實作：WebSocket（目前 codebase 無 WS endpoint）。

- SSE event 類型（現況）
  - `token`：逐 token 輸出（`{"text": "..."}`）
  - `plan`：需確認的命令計畫卡（含 `plan_card/command/args/project_id/chat_id`）
  - `result`：命令執行結果（JSON object）
  - `error`：錯誤訊息（`{"message": "..."}`）
  - `done`：流程終態（`status` + chat/project/run 資訊，依情境回傳）

- 一般 API 資料格式
  - `Content-Type: application/json`
  - 錯誤慣例：`{"message": "..."}`

### 5.5 元件命名與狀態管理規範
- 元件命名
  - 延續既有 class 命名風格：`區塊` + `__子元素` + `--狀態`（可逐步 BEM 化）。
  - DOM `id` 僅給需要 JS 直接選取的控制點，避免濫用。
  - 新增 UI 區塊時，命名需可讀且對應領域（chat/context/graph/docs/tools...）。

- 狀態管理
  - 以「最小可行」為原則：單頁先用區域 `state` 物件，避免過早引入外部框架。
  - 非同步流程（streaming、長任務）必須有可見狀態（progress/loading）且不可鎖死 UI。
  - 需持久化的資料（chat history、events、run artifacts）統一由後端 session/project store 管理，不在前端自行定義第二份真相。
  - 錯誤不得吞沒：UI 要顯示可理解訊息；技術細節寫入後端 logs。
