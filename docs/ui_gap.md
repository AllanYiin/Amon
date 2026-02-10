# Vibe Coding 開發規範

## 目的
本文件先做現況盤點與規格落差分析（不大改程式），對照 Amon UI 規格整理可執行的最小可行交付（MVP）順序。

## 目前 UI 盤點

### 1) 使用的框架與路由方式
- **前端框架**：未使用 React/Vue 等框架，採 **靜態 HTML + 原生 JavaScript**；`index.html` 直接維護 `state` 物件與 DOM 事件。 
- **UI 路由方式**：非 SPA router，屬於多頁靜態檔（`index.html` / `project.html` / `single.html`）。
- **後端路由方式**：`AmonUIHandler` 以 `SimpleHTTPRequestHandler` 提供靜態檔，API 走 `/v1/*`（例如 `/v1/projects`、`/v1/projects/{id}/context`、`/v1/chat/stream`）。

### 2) 主要頁面 / 元件
- **頁面**
  - `index.html`：主 Chat UI（含專案選擇、聊天時間線、Plan Card、Context/Graph/Docs 分頁）。
  - `project.html`：專案工作台展示頁（多數功能為 disabled 或示意）。
  - `single.html`：單一模式展示頁（送出功能未串接 API）。
- **主要元件（以語意區塊 class 為主）**
  - Chat：`chat-panel`、`chat-timeline`、`chat-bubble`、`chat-input`
  - Plan：`plan-card`
  - Context 右側：`context-panel` + tabs（`context` / `graph` / `docs`）
  - Graph：`graph-preview` + `graph-code`（Mermaid）
  - Docs：`docs-list`
  - 通知：`toast`
  - 長任務狀態：`stream-progress`

### 3) 是否有 SSE / WebSocket 訂閱 events
- **SSE：有**
  - 前端使用 `EventSource('/v1/chat/stream?...')`。
  - 目前前端監聽事件：`token`、`notice`、`plan`、`result`、`error`、`done`。
  - 後端 `ui_server` 有 `text/event-stream` 的 SSE 實作。
- **WebSocket：無**
  - `src/amon/ui/` 與 `src/amon/ui_server.py` 未見 WebSocket 相關實作或路由。

### 4) 功能現況（你指定的項目）
- **Chat streaming**：✅ 已有（token 串流 + 進度條顯示）。
- **Plan Card**：✅ 已有（顯示 + confirm/cancel 呼叫 `/v1/chat/plan/confirm`）。
- **Artifact**：⚠️ 後端有 artifacts 能力，但 UI 未見 artifact 清單/預覽/下載入口。
- **Graph view**：✅ 已有（Context 分頁顯示 Mermaid preview 與 code）。
- **Docs browser**：🟡 基礎清單已有（`docs-list`），但僅列檔名，尚無檢視內容/搜尋/分頁等瀏覽能力。
- **Billing view**：❌ 尚無 UI。

## 與 Amon UI 規格的 Gap 清單（逐項）

1. **Artifact 視圖缺口（中）**
   - 現況：主 UI 無 artifact 區塊，使用者看不到 run 產物（檔案、路徑、下載）。
   - 規格期待：可檢視 run artifacts，並作為 chat / graph 的結果呈現一部分。

2. **Docs browser 能力不足（中）**
   - 現況：僅有 `docs` 檔名列表。
   - 缺口：缺少點擊開啟、內容預覽、錯誤提示、（至少）基本檔案瀏覽流程。

3. **Billing view 缺口（中）**
   - 現況：無 billing dashboard。
   - 規格期待：對 `logs/billing.log` 做安全展示（避免敏感資訊暴露）。

4. **Single / Project 頁面與真實 API 串接不足（中）**
   - 現況：`single.html` 明示未串接 API；`project.html` 多處示意與 disabled。
   - 影響：目前可用主流程集中在 `index.html`，其他頁面仍偏展示性質。

5. **事件可觀測性仍可補強（低）**
   - 現況：SSE 已具備，但 UI 主要聚焦 chat bubble；缺少明確 event timeline / run 狀態面板（例如 token/result/error/done 對應可追蹤記錄）。
   - 風險：除錯與追蹤使用者體驗事件較不直觀。

6. **WebSocket 非必要但屬擴充缺口（低）**
   - 現況：僅 SSE，無 WS。
   - 判定：依規格「現況」可接受；若未來有雙向互動需求（例如多人協作編輯）再評估，不列 MVP 必做。

## 建議實作順序（最小可行交付）

### Phase 1（先補可用性）
1. **Docs browser MVP**
   - 在現有 `docs-list` 上加入「點擊檔名 -> 右側預覽內容」與失敗提示（toast）。
   - 原則：沿用既有 `/v1/*`，不導入前端框架。

2. **Artifact MVP**
   - 在 `index.html` 增加 Artifact 分頁（或 Context 下子區塊）。
   - 先支援「列出最近 run 產物 + 下載連結 + 基本預覽（文字/圖片/PDF）」。

### Phase 2（補規格完整性）
3. **Billing view MVP（唯讀）**
   - 新增 Billing 分頁，提供基礎列表（時間、模型、token、成本）。
   - 安全策略：欄位白名單輸出，預設隱藏敏感欄位；錯誤訊息友善化。

4. **Project / Single 頁面去示意化**
   - 先把 `single.html` 接上既有 `/v1/chat/stream`。
   - `project.html` 先導入唯讀資料（任務/文件/run 狀態）再逐步啟用互動。

### Phase 3（可觀測性與體驗）
5. **Event timeline / run status 面板**
   - 顯示 `plan/result/error/done` 結構化紀錄，提升排錯能力。

6. **進階：WebSocket（可選）**
   - 僅在確定需要雙向即時協作時再導入；目前先維持 SSE 降低複雜度。

## 結論
- 現況最成熟的是 `index.html` 主流程（Chat streaming + Plan Card + Graph + Docs 清單）。
- 與規格最大差距是 **Artifact / Billing / Docs 深度瀏覽**，建議先做這三塊的 MVP，再處理次要頁面整合與事件可觀測性。
