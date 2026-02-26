# Phase 0：Graph / Chat / Context 護欄與驗收基準

> 目標：建立可重現的手動回歸流程、呼叫點盤點與可回滾策略。
> 原則：Phase 0 不變更 API contract、不改 UI 對外行為，只補齊文件與 dev-only 診斷輔助。

## 1) Graph page（`#/graph`）回歸步驟

1. 進入 `#/graph` 頁面。
2. 檢查 **Run 下拉選單**是否有列出 runs。
   - 預期：可列出 `run.id|run.status`。
   - 無 run 時預期：顯示「尚無歷史 Run」。
3. 切換 run。
   - 預期：可載入 `graph_mermaid`，`#graph-preview` 會渲染 SVG。
   - 若 run 無 graph：顯示「此 Run 尚無流程圖資料」。
4. 點擊 node list（`#graph-node-list`）中的 node。
   - 預期（理想）：應開啟 node detail drawer。
   - **現況（Phase 0 記錄）**：Graph view 目前只更新 store 的 `graphView.selectedNode`，但 drawer 顯示控制在 `bootstrap.js` 走 `state.graphSelectedNodeId/elements.graphNodeDrawer` 路徑，兩邊狀態來源不一致，可能出現「點了 list 但 drawer 沒開」的情況。
5. 點擊 mermaid 圖上的 node。
   - 預期（理想）：與 list 點擊一致，能開 drawer。
   - **現況（Phase 0 記錄）**：Graph view 目前未綁定 SVG node click 事件，常見情況是「圖上點擊沒有反應」。
6. 檢查 node status 顯示一致性。
   - 預期（理想）：list status 與右側 inspector / stream event 同步。
   - **現況（Phase 0 記錄）**：list 使用 graph payload 的 `node.status/state` 正規化（非 running/succeeded/failed 會落到 pending），可能與 `node_states` 的即時狀態不同步或看起來停在 pending。

## 2) Chat page 右側 graph / inspector 回歸步驟

1. 進入 `#/chat`，送出一則訊息建立 run。
2. 觀察右側（或相關 inspector）是否隨事件更新 `node_states`。
   - 預期：run 開始後，能看到 run id / node 狀態逐步更新。
3. 當 run `done/error` 後，檢查是否刷新為最終狀態。
   - 預期：run meta 與 node 狀態進入結束狀態，且後續切到 graph 頁能對到同一 run。

## 3) Context page（`#/context`）回歸步驟

1. 進入 `#/context` 並確認已選 project。
2. `load stats`：
   - 預期：載入 context 與 stats（容量、剩餘、估算成本等）並更新 UI 區塊。
3. `save`：
   - 預期：儲存草稿成功，顯示成功 toast 與更新草稿時間。
4. `clear(project)`：
   - 預期：清空專案 context，editor 清空，儀表區轉為 unavailable。
5. `clear(chat)`：
   - 預期：清空本次 chat context，editor 清空，並重新 refresh stats。

## 4) 回滾策略（Phase 可獨立 revert）

- **Phase 0（本次）**：僅新增文件 + dev-only log。
  - 快速回滾：
    1. `git revert <phase0_commit_sha>`（建議，保留歷史）
    2. 或臨時停用 debug：移除 URL `?ui_debug=1` 並清掉 `localStorage['amon.ui.debug']`
- **後續每個 phase** 都應遵守：
  - 一個 phase 對應一個（或少數）可獨立還原的 commit。
  - 若新功能有 flag，預設關閉；異常時先關 flag 回到上一版行為，再進行 hotfix。

## 5) 全 repo 呼叫點盤點（ripgrep）

以下使用 `rg -l` 盤點，列出檔案路徑。

### 5.1 `/v1/context/clear` / `context/clear` / `clearContext(`

- `src/amon/ui/static/js/domain/contextService.js`
- `src/amon/ui/static/js/views/context.js`
- `src/amon/ui_server.py`

### 5.2 `/v1/runs`、`runs/`、`getGraph(`、`listRuns(`

- `docs/chat_ui_router_api_design.md`
- `docs/frontend-architecture.md`
- `docs/phase5-second-split-instructions.md`
- `docs/specs/sandbox_integration.md`
- `src/amon/run/context.py`
- `src/amon/ui/static/js/domain/artifactsService.js`
- `src/amon/ui/static/js/domain/graphService.js`
- `src/amon/ui/static/js/domain/runsService.js`
- `src/amon/ui/static/js/store/slices/runsSlice.js`
- `src/amon/ui/static/js/views/graph.js`
- `src/amon/ui_server.py`
- `tests/test_ui_async_api.py`
- `tests/test_ui_shell_smoke.py`

### 5.3 `node_states`、`graphRunId`、`selectedNode`、`graphNodeDrawer`

- `src/amon/ui/static/js/bootstrap.js`
- `src/amon/ui/static/js/store/app_state.js`
- `src/amon/ui/static/js/store/elements.js`
- `src/amon/ui/static/js/views/chat.js`
- `src/amon/ui/static/js/views/graph.js`
- `src/amon/ui_server.py`
- `tests/test_ui_async_api.py`

### 5.4 Chat route / `chat_id` 來源（hash route 解析）

- `docs/chat_context_root_cause_report.md`
- `docs/frontend-architecture.md`
- `docs/testing_continuation_guard.md`
- `docs/ui-refactor/00_spec.md`
- `src/amon/ui/index.html`
- `src/amon/ui/static/js/api.js`
- `src/amon/ui/static/js/bootstrap.js`
- `src/amon/ui/static/js/core/store.js`
- `src/amon/ui/static/js/router.js`
- `src/amon/ui/static/js/views/chat.js`
- `src/amon/ui/static/js/views/docs.js`

## 6) Phase 0 開發期 debug 輔助（dev-only）

- 控制方式（opt-in）：
  - URL query：`?ui_debug=1`
  - 或 LocalStorage：`localStorage.setItem('amon.ui.debug','1')`
- 在 `Graph/Chat/Context` view 初始化時印出：
  - `project_id`
  - `run_id`
  - `chat_id`
  - `node_states_count`
- 預設關閉，不會在 production 無條件輸出 console log。

## 7) Phase 2：Graph Node Drawer 串接驗收步驟

1. 進入 `#/graph`，選擇任一有節點的 run。
2. 點擊 node list 任一 node。
   - 預期：`graph-node-drawer` 開啟，顯示 `title / status / inputs / outputs / events`。
   - 預期：被點擊的 list item 帶有 selected 樣式。
3. 點擊 Mermaid SVG 上任一 node。
   - 預期：與 list 點擊共用 `selectNode(nodeId)` 路徑，會開啟同一 drawer 並顯示對應 node detail。
   - 預期：SVG node 也有 selected 樣式，不影響既有 status class。
4. 測試 drawer 關閉動作：
   - 點 close button → drawer 關閉。
   - 按 `ESC` → drawer 關閉。
   - 點擊 drawer 外背景區域（非 drawer、非 graph node 互動元素）→ drawer 關閉。
5. 測試 run 切換：
   - 切換 run 後，selected 狀態與 drawer 應重置，避免殘留上一個 run 的 node detail。

## 8) Phase 3：Graph page 自動同步刷新驗收步驟

1. 開啟 `#/graph` 並選定一個 run（建議同時開啟 `?ui_debug=1` 觀察 diagnostics）。
2. 在 chat 流程觸發 run / run.update / node.update / done 類型事件。
3. 驗證自動刷新：
   - 若事件 `run_id` 等於目前 Graph 選取 run：應自動 refresh current graph（node list + SVG 狀態同步更新）。
   - 若事件 `run_id` 不同：應只 refresh run list，不應強制切換目前選取 run。
4. 驗證節流：
   - 高頻事件時，Graph 不應狂閃或連續重繪到不可操作；更新應以節流批次進行。
5. 驗證 drawer 保留：
   - drawer 開啟且 `selectedNodeId` 仍存在時，自動 refresh 後 drawer 應保持開啟並刷新內容（不應被關掉）。

## 9) Phase 4：Context clear(chat) 帶 chat_id 驗收步驟

1. 進入 `#/context` 並確認已選 project。
2. 檢查「清空本次對話」按鈕狀態：
   - 若目前沒有 `chat_id`：按鈕應 disabled，提示需先有聊天 session。
   - 若已有 `chat_id`：按鈕可操作。
3. 送出 clear(chat)（帶 `chat_id`）：
   - 預期 request body 含 `scope=chat, project_id, chat_id`。
   - 預期只清除該 `chat_id` 對話資料，不影響同專案其他 chat。
4. 送出 clear(chat) 且缺 `chat_id`：
   - 預期後端回 400，前端顯示可理解錯誤，不可默默改清 project。
5. clear(project) 驗證：
   - 預期仍只清 project context，既有行為不變。

## 10) Phase 5：收斂與可維護性驗收步驟（最新行為）

1. **單一權威狀態 mapping**
   - 驗證 Graph 與 Chat 右側 inspector 的 node status 標籤都來自 `graphRuntimeAdapter` 的 `statusUi`。
   - 檢查不應再出現各自私有 `pending/running/...` label mapping（僅 adapter 保留權威規則）。

2. **Graph page 自動刷新（節流 + 可操作性）**
   - 開著 `#/graph` 觸發高頻 `run.update` / `node.update`：
     - Run 非當前選取 run：僅刷新 run 下拉。
     - Run 為當前選取 run：刷新 current run graph（含 node_states）。
   - 預期：畫面不應無限重繪；refresh 維持節流（約 450ms）。

3. **Graph drawer 穩定性（刷新中不中斷）**
   - 打開某個 node drawer 後觸發同步更新。
   - 預期：drawer 不會被強制關閉；若選取節點仍存在，內容會更新且 selected 樣式保留。

4. **增量更新策略（避免不必要 SVG 重繪）**
   - 在 mermaid 圖結構（graph_mermaid）未變化時，僅更新 node status class / list status，不重新 render SVG。
   - 在 mermaid 圖結構變更時，才走完整 render + re-bind click。

5. **訂閱釋放與 leak 檢查（dev-only）**
   - 使用 `?ui_debug=1` 或 `localStorage['amon.ui.debug']=1`。
   - 進入/離開 `#/graph` 多次，確認 console 有 `graph.live-subscriptions` subscribe/unsubscribe 記錄，且離開路由後 active_subscribers 會回到 0。

