# Phase 5.2 第二段拆分執行指引（Amon UI）

> 適用範圍：`src/amon/ui/static/js/*`。
> 目標：在不引入 build step 的前提下，將目前 `bootstrap.js` 的分頁職責與資料流進一步下沉至 `views/*` + `domain/*` + `store/*`，讓入口僅保留 composition root。

## 5.2-0 先讀現況（盤點結論）

目前程式結構已具備 Phase 5 第一段成果：

- 入口：`app.js` 僅呼叫 `bootstrapApp()`。
- Core：`core/bus.js`、`core/store.js` 已存在。
- Domain：`domain/services.js` 與各 service 已存在。
- View：`views/chat|context|graph|docs|billing|logs|config|tools` 已存在，但成熟度不一致。
- Layout：`layout/sidebar|header|inspector|splitPane` 已存在。

仍待完成的第二段拆分缺口：

1. `bootstrap.js` 仍包含大量 view 專屬 render / event 綁定邏輯。
2. `config.js` / `tools.js` 仍偏薄，依賴 bootstrap 內部 helper。
3. i18n 字串仍有散落硬編字串。
4. 部分模組存在 store patch 與 DOM 操作混合，邊界可再收斂。

---

## 5.2-1 模組邊界與契約（先立規則）

### View 契約（`views/*.js`）

每個 view 必須 export：

- `id: string`
- `route: string`
- `mount(ctx): void`
- `unmount(): void`
- `onRoute(params, ctx): void | Promise<void>`

`ctx` 必須只依賴以下欄位：

```js
{
  rootEl,
  store,
  services,
  ui,      // toast/modal/tabs/accordion
  t,
  bus
}
```

禁止事項：

- 在 view 內直接 `fetch`。
- 在 view 內直接 mutate 全域 state 物件。
- 未提供 unmount 清理事件監聽與 stream controller。

### Service 契約（`domain/*Service.js`）

- `createXService({ api })` 型式。
- 只負責 API 呼叫 + normalize。
- 不碰 DOM、不 dispatch store。

### Bootstrap 契約（`bootstrap.js`）

只做：

- 初始化 `api/store/bus/i18n/ui/layout/router`。
- 註冊 view。
- 進行全域錯誤邊界綁定。

不做：

- 分頁細節渲染。
- 分頁內部事件綁定。
- 分頁專用資料組裝。

---

## 5.2-2 Core 層收斂順序

1. **constants 正規化**：將 status level / badge class / status i18n key 只留在 `constants/status.js`。
2. **utils 統一**：`format.js`、`dom.js`、`clipboard.js` 必須被 views/layout 重用，避免重複 helper。
3. **store action 命名一致**：採 `domain/action`（例如 `runs/setCurrent`、`docs/setCurrent`）。
4. **bus 命名一致**：採 `domain:action`（例如 `view:mounted`、`run:changed`）。

---

## 5.2-3 Domain 收斂順序

優先把 bootstrap 仍殘留的 API 呼叫搬到 services，並遵循 normalize shape：

- run: `{ id, status, createdAt }`
- artifact: `{ id, name, mime, size, createdAt, url }`
- doc: `{ id, name, path, updatedAt, content? }`

錯誤處理規範：

- service 拋出原始錯誤（包含 message）。
- view 顯示使用者可讀 toast。
- console 保留技術細節。

---

## 5.2-4 Layout 分拆完成定義

- `sidebar.js`：僅處理導航與 active 樣式。
- `header.js`：僅 render pills 與 project selector（資料來自 store）。
- `inspector.js`：僅處理 tab/collapse/resize 與持久化。

檢查點：layout 不可直接呼叫 services。

---

## 5.2-5 分頁職責下沉（建議執行順序）

1. `context.js`
2. `docs.js`
3. `billing.js`
4. `logs.js`
5. `graph.js`
6. `chat.js`（最後）

每搬完一頁都要完成以下最小驗收：

- 切入頁面可載入。
- 切走再切回不重複綁事件。
- router back/forward 可用。

---

## 5.2-6 i18n / A11y / RWD 收尾標準

### i18n

- UI 可見字串使用 `t()`。
- status、empty state、button、tooltip 不留硬編字串。

### A11y

- Sidebar active 使用 `aria-current`。
- Tabs 設 `role="tablist" / "tab" / "tabpanel"`。
- Modal 支援 focus trap + Esc。
- Toast `aria-live="polite"`。

### RWD

- `< 768px`：sidebar 預設收合。
- inspector 預設收合或抽屜化。
- 長內容水平捲動，避免破版。

---

## 5.2-7 清理、文件、回滾

1. `bootstrap.js` 僅保留 composition root。
2. `project.html` / `single.html` 保持 thin redirect（或移除並同步文件）。
3. 更新 `docs/frontend-architecture.md`：
   - 責任邊界
   - 新增 view/service 的操作手冊
   - debug 手冊
4. 建立回滾計畫：
   - 保留穩定 tag
   - 失敗時可切回前版 bootstrap

---

## 手動 QA Checklist（最終回歸）

1. Router：任一路由可 back/forward。
2. Chat：可送出訊息、可看到 streaming、完成後狀態更新。
3. Context：可儲存、可清空、清空有 confirm。
4. Graph：可互動（縮放/拖曳/節點點擊）。
5. Artifacts：可清單、可預覽、可下載。
6. Docs：可篩選、可預覽 markdown/code、可高亮。
7. Billing：摘要 + 圖表可顯示。
8. Logs：可查詢並更新。
9. RWD：手機寬度主要流程不破版。
10. A11y：鍵盤可操作主要控制（nav/tab/modal/copy）。

---

## 風險與設計取捨

- 取捨：第二段拆分採「頁面逐步搬移」，不一次改完，優先降低回歸風險。
- 風險：過渡期可能同時存在 bootstrap 舊邏輯與 view 新邏輯，需每完成一頁就刪除舊碼避免雙實作。
- 回滾：若任一 view 模組失敗，先回到前一個穩定 commit/tag，再逐頁重新導入。
