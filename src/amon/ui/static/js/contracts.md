# Amon UI 模組契約（5.2-1）

本文件定義 `static/js` 前端模組邊界，供後續拆分與維護依循。

## A) View 介面（`/views/<name>.js`）

每個 view 都必須 `export` 同一份契約：

- `id: string`（唯一識別，例如 `chat`）
- `route: string`（路由路徑，例如 `/chat`）
- `mount(ctx): void`（進入後第一次載入時初始化）
- `unmount(): void`（離開 view 時釋放 listener/資源）
- `onRoute(params, ctx): void | Promise<void>`（每次路由進入都可觸發資料載入）

`ctx` 統一為：

- `rootEl`: 該 view 的容器元素
- `store`: 全域 store
- `services`: domain services
- `ui`: 共用 UI 元件（toast/modal/tabs/accordion…）
- `t`: i18n 翻譯函式
- `bus`: event bus

## B) Domain Service 介面（`/domain/<domain>Service.js`）

- 模組介面統一為：`create<Domain>Service({ api })`
- 責任僅限：呼叫後端 API、回傳資料、最小 normalize
- 不允許：
  - 操作 DOM
  - 直接改寫全域 state

## C) Composition Root（`bootstrap.js` + `app.js`）

`bootstrap.js` 只負責組裝與初始化：

- 建立 `api / store / bus / i18n / ui components`
- 建立 router 與註冊 views
- 建立 layout 控制（sidebar / inspector / header）

`app.js` 僅保留入口 bootstrap：

- import `bootstrapApp`
- 呼叫 `bootstrapApp()`

`bootstrap.js` 不應新增以下內容：

- 某單一 view 的大量 render 細節
- 某單一 domain 的複雜資料組裝
- 直接綁定單一 view 內大量事件（應下沉到 `view.mount`）

> 過渡期可保留既有邏輯，但新功能必須優先依契約落地，並逐步將舊程式碼搬遷至 view 與 domain service。
