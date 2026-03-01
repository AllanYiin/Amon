# UI Offline Vendor 說明

本文件說明 UI 在離線情境下所使用的本地 vendor 資產，目標是讓 Chat 與 Graph 頁在無外網時仍可載入且不報前端錯誤（模型端連線不在此範圍）。

## 本次固定為本地載入的第三方庫

以下四個 UI 依賴已使用 `src/amon/ui/static/vendor/` 本地檔案：

1. DOMPurify
   - Global API：`window.DOMPurify`
   - 檔案：`src/amon/ui/static/vendor/dompurify/purify.min.js`
   - 版本：`3.1.6`
2. marked
   - Global API：`window.marked`
   - 檔案：`src/amon/ui/static/vendor/marked/marked.min.js`
   - 版本：`12.0.2`
3. highlight.js
   - Global API：`hljs`
   - 檔案：
     - `src/amon/ui/static/vendor/highlight.js/highlight.min.js`
     - `src/amon/ui/static/vendor/highlight.js/github.min.css`
   - 版本：`11.10.0`
4. Chart.js
   - Global API：`Chart`
   - 檔案：`src/amon/ui/static/vendor/chart.js/chart.umd.min.js`
   - 版本：`4.4.3`

> 來源與版本清單同步記錄於：`src/amon/ui/static/vendor/vendor-manifest.json`。

## `index.html` 載入策略

- `src/amon/ui/index.html` 對上述四個庫維持原有 API 使用方式（`window.DOMPurify` / `window.marked` / `hljs` / `Chart`），僅使用本地 `static/vendor` 路徑載入。
- 未修改既有呼叫端行為，僅調整與明確化載入來源。

## 離線驗收（DoD 對應）

1. 啟動 UI：
   ```bash
   amon ui --port 8000
   ```
2. 斷網（或在瀏覽器 DevTools 啟用 Offline）。
3. 打開 `http://localhost:8000`，確認：
   - Chat 頁可正常進入，Console 沒有 `DOMPurify` / `marked` / `hljs` not defined 錯誤。
   - Graph 頁可正常進入，與圖形互動流程不因上述四個庫缺失而報錯。
4. Network 面板可確認上述資源由本地路徑提供，不依賴 CDN。
