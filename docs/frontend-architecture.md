# Amon UI 前端架構維護指南

本文件對應目前 UI 單一入口架構：**`index.html + hash routes`**。

> 入口規範：
> - 唯一正式入口：`src/amon/ui/index.html`
> - `src/amon/ui/project.html` 與 `src/amon/ui/single.html` 僅保留最薄 redirect，用於相容舊連結。

## 1. 目錄結構

```text
src/amon/ui/
├─ index.html                  # 單一入口頁（shell + 各 view container）
├─ project.html                # 相容 redirect -> index.html#/context
├─ single.html                 # 相容 redirect -> index.html#/chat
├─ styles.css
└─ static/js/
   ├─ app.js                   # 只做 bootstrap 呼叫
   ├─ bootstrap.js             # composition root（組裝 router/store/views）
   ├─ router.js
   ├─ core/
   │  ├─ store.js
   │  └─ bus.js
   ├─ domain/                  # service 層（API 封裝）
   ├─ store/                   # state slice + element collection
   ├─ layout/                  # shell/header/sidebar/inspector
   └─ views/                   # chat/context/graph/docs/billing/logs/config/tools
```

## 2. View / Service / Store / Bus 邊界

- **View (`views/*.js`)**
  - 負責畫面呈現、事件綁定、使用者互動流程。
  - 可呼叫 `services` 取資料、透過 `store` 讀寫 UI 狀態。
  - 不直接耦合其他 view 的 DOM 細節。

- **Service (`domain/*Service.js`)**
  - 負責呼叫 `/v1/*` API 與最小資料轉換。
  - 不操作 DOM、不直接操作全域 UI 元件。

- **Store (`core/store.js` + `store/slices/*.js`)**
  - 負責共享狀態（project、run、docs、context、layout…）。
  - View 透過 store subscription 或 patch/update 反應變化。

- **Bus (`core/bus.js`)**
  - 負責跨模組事件溝通（例如 run 狀態更新、通知 inspector 刷新）。
  - 用於降低 view 彼此直接依賴。

## 3. 常見修改範例

### 範例 A：新增一個 view（以 `alerts` 為例）

1. 建立 `src/amon/ui/static/js/views/alerts.js`，輸出 view contract：`id/route/mount/unmount/onRoute`。
2. 在 `index.html` 增加 view root（例如 `<section id="alerts-page" ...>`）與側邊導覽 link（`href="#/alerts"`）。
3. 在 `bootstrap.js`：
   - import 新 view。
   - 加入 `VIEW_ROOTS` 與 `SHELL_VIEW_HANDLERS`。
4. 若需 API，新增 `domain/alertsService.js` 並在 `domain/services.js` 註冊。
5. 補 smoke test（至少驗證 hash route 與 DOM token 存在）。

### 範例 B：在 header 增加一個狀態 pill

1. 在 `index.html` header 區塊加上新 pill 容器（含 `id`）。
2. 在 `layout/header.js` 擴充 render/update 邏輯。
3. 在 `bootstrap.js` 初始 `layout` state 增加對應欄位。
4. 需要後端資料時，從 service 拉取後 patch 到 store，再由 header layout 反映。

## 4. Debug 指南

### 4.1 看 store state

- 在瀏覽器 DevTools Console 執行（建議暫時打開對應 debug log）：
  - 於 `bootstrap.js` 內對 `appStore.getState()` 做 breakpoint / `console.debug`。
  - 對特定 slice 觀察 patch 前後差異（例如 `layout`, `runs`, `context`）。

### 4.2 追 bus events

- 在 `core/bus.js` 的 emit/subscribe 位置設 breakpoint。
- 搜尋事件名稱來源（`rg "bus\.emit|bus\.on" src/amon/ui/static/js`）。
- 先確認事件 payload 是否完整，再確認 view subscriber 是否有解除註冊。

### 4.3 常見故障快速定位

- **畫面沒切換**：先看 hash 是否正確，再檢查 router parse 與 view mount。
- **資料沒更新**：先看 service response，再看 store patch 是否成功。
- **stream 卡住**：檢查 SSE endpoint 與 `done/error` 事件是否到達。

## 5. 手動回歸測試清單（可逐項點檢）

> 建議每次前端重構後完整跑一次。

1. **Router**：任意頁面切換後，瀏覽器 Back/Forward 都能正確回到前一個 hash route。
2. **Chat**：送出訊息可看到 streaming；run 狀態 queued/running/succeeded/failed 顯示正確。
3. **Context**：可新增內容、儲存草稿、清空（含 confirm modal）。
4. **Graph**：可縮放/拖曳；點節點有互動結果，或無資料時有清楚提示。
5. **Artifacts**：可載入清單、開啟預覽、下載檔案。
6. **Docs**：可載入清單、預覽 Markdown 與 code highlight。
7. **Billing**：可看到數字摘要與圖表區塊正常渲染。
8. **Logs**：可載入 logs/events，或串流更新可見。
9. **RWD**：手機寬度下 sidebar/inspector 開關行為正確、不遮擋主要操作。
10. **A11y**：鍵盤可操作主要控制項，focus 樣式可見。

## 6. 風險與回滾策略

### 6.1 主要風險

- ESM 模組載入失敗（路徑錯誤、快取舊版、語法錯誤）會導致 UI 無法啟動。
- 某 view 初始化錯誤可能阻斷整體 bootstrap 流程。

### 6.2 快速回滾方案

1. **Git 回滾**：保留可用版本 tag（建議每次 UI 重構前先打 tag），異常時可即刻 `git checkout <tag>` 回復。
2. **分支回滾**：保留上一版穩定分支（例如 `release/ui-stable`），用於緊急 hotfix 覆蓋部署。
3. **入口 fallback**：可暫時把 `app.js` 指回既有穩定 bootstrap 檔（例如 `bootstrap.legacy.js`）；僅作 emergency 用，修復後再回主線。

> 注意：fallback 檔案若含舊實作，需明確標註淘汰期限，避免形成雙實作長期共存。
