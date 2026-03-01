# Graph Debug 手動驗收與排查指南

> 目的：提供 Graph 頁面（Mermaid + svg-pan-zoom）問題的標準化手動驗收流程、失敗排查清單，以及目前 `index.html` 使用 CDN 的風險與修正方向。

## 手動驗收步驟（至少 8 步）

1. **啟動 UI Server**
   - 在 repo root 執行：
     ```bash
     amon ui --port 8000
     ```
   - 確認終端機顯示服務已啟動，且可連線 `http://localhost:8000`。

2. **開啟 Graph 頁**
   - 用瀏覽器進入 `http://localhost:8000`。
   - 從側欄點選「流程圖」，或直接前往 `#/graph`。

3. **確認 Mermaid 是否載入**
   - 打開瀏覽器 DevTools Console，輸入：
     ```js
     window.__mermaid
     ```
   - 預期：回傳 `object`（非 `undefined` / `null`）。

4. **確認 svg-pan-zoom 是否載入**
   - 在 Console 輸入：
     ```js
     window.svgPanZoom
     ```
   - 預期：回傳 `function`（非 `undefined`）。

5. **確認 Graph 是否渲染成功**
   - 在 Console 執行：
     ```js
     document.querySelector('#graph-preview svg')
     ```
   - 預期：回傳 `SVGSVGElement`；代表 `#graph-preview` 內已有 `svg`。

6. **確認節點可點擊（Drawer 可開啟）**
   - 在 Graph 畫面中點擊任一節點（DOM 通常是 `g.node`）。
   - 預期：右側或對應位置的節點資訊 drawer / 詳細面板開啟，顯示該節點內容。

7. **確認節點狀態 class 有套用**
   - 在 Elements 面板選一個節點 `g.node`，檢查其 `class`。
   - 預期：class 內包含 `node-status--*`（例如 `node-status--running`、`node-status--done`、`node-status--failed` 等）。

8. **確認增量更新（不閃爍）**
   - 觸發一次 run（讓節點狀態有變化）。
   - 觀察 Graph 更新過程：
     - 節點狀態應刷新（class 變化可追蹤）。
     - 不應出現整張圖反覆清空重繪造成明顯閃爍。

9. **補充檢查：互動能力未失效**
   - 在圖上嘗試拖曳、縮放（滑鼠滾輪或控制按鈕，如 UI 有提供）。
   - 預期：平移縮放正常，且不影響節點點擊事件。

## 常見失敗排查

> Graph 頁目前會明確區分四種狀態，請先對照 UI 文案再往下排查。

| 狀態代碼 | UI 文案 | 代表意義 |
| --- | --- | --- |
| A | 此 Run 尚無流程圖資料 | 後端回傳 `graph_mermaid` 為空字串或缺失。 |
| B | Mermaid 未載入（可能離線或資源被擋） | 前端已拿到 `graph_mermaid`，但 `window.__mermaid` 不存在。 |
| C | 流程圖渲染失敗 | `window.__mermaid.render(...)` 丟出錯誤。 |
| D | 流程圖已渲染但無法識別節點 | SVG 已產生，但 `g.node` 結構不符合目前綁定規則。 |

### A) 後端 `graph_mermaid` 為空/缺失（真正沒資料）

**UI 訊息**
- 「此 Run 尚無流程圖資料」
- 「請先查看下方 graph-code 區塊是否有內容。」

**排查重點**
1. 先確認 `graph-code` 區塊內容是否為空。
2. 檢查該 Run 的 API 回應，確認 `graph_mermaid` 是否真的沒有值。
3. 若預期應該有圖，回頭檢查 run pipeline 是否有產生 graph payload。

### 1) CDN 被擋／離線，造成 `window.__mermaid` 不存在

**症狀**
- `window.__mermaid` 為 `undefined`。
- Console 出現 `Failed to load module script`、`ERR_BLOCKED_BY_CLIENT`、`net::ERR_INTERNET_DISCONNECTED` 等。

**排查步驟**
1. 開啟 DevTools → Network，重新整理頁面。
2. 篩選 `mermaid` / `jsdelivr`，確認請求是否 `200`。
3. 若被公司防火牆、AdBlock、離線模式阻擋，先切換網路或停用阻擋規則再測。

**處置建議（短期）**
- 在驗收環境白名單 `cdn.jsdelivr.net`。
- 先確認同網段是否可正常載入 CDN 腳本。

**UI 對應（B）**
- 「Mermaid 未載入（可能離線或資源被擋）」
- 「請嘗試重新整理頁面後再試一次。」
- 頁面會提供「重新整理頁面」按鈕。

### 2) Mermaid render 丟錯（如何抓錯誤）

**症狀**
- `window.__mermaid` 存在，但圖沒有渲染。
- Console 有 Mermaid parser / render exception。

**排查步驟**
1. 在 Console 保留錯誤（Preserve log 開啟），重新觸發 Graph 渲染。
2. 尋找包含 `mermaid`、`parse`、`render` 關鍵字的 error stack。
3. 可手動包一層偵錯：
   ```js
   window.addEventListener('error', (e) => {
     if (String(e?.message || '').toLowerCase().includes('mermaid')) {
       console.error('[graph-debug] mermaid window error:', e.error || e.message);
     }
   });
   ```
4. 若有來源圖文法，先驗證是否存在非法語法（例如未轉義字元、錯誤箭頭語法）。

**UI 對應（C）**
- 「流程圖渲染失敗」
- 「錯誤摘要：<error.message>」

**建議手動製造驗證**
- 把 `graph_mermaid` 改成非法語法（例如 `flowchart TD\nA-->`），確認 UI 顯示 C 訊息，且 Console 有對應錯誤紀錄。

### 3) SVG 有出現，但沒有 `g.node`（Mermaid 版本差異）

**症狀**
- `#graph-preview svg` 存在。
- `document.querySelectorAll('#graph-preview g.node').length === 0`。

**可能原因**
- Mermaid major/minor 版本導致節點 DOM 結構變化。
- 選擇器綁定過度依賴特定 class 名稱。

**排查步驟**
1. 在 Elements 直接展開 `svg`，查看實際節點標記與 class。
2. 用較寬鬆 selector 驗證（如 `#graph-preview g`、`[id^="flowchart-"]` 等）確認節點是否存在但 class 改名。
3. 比對目前版本與既有測試／實作假設是否一致。

**UI 對應（D）**
- 「流程圖已渲染但無法識別節點」
- 「可能是 Mermaid 版本差異，請比對 g.node 結構。」

**補充說明**
- 這種情況下 SVG 仍會顯示，Node List / Drawer 仍可從左側清單操作。


## 本地 vendor 驗證（離線可用）

1. 開啟 DevTools → Network，勾選 `Disable cache` 後重新整理頁面。
2. 在過濾器輸入 `jsdelivr`。
3. 預期：**不應看到** `mermaid` 與 `svg-pan-zoom` 對 `cdn.jsdelivr.net` 的請求。
   - 若有 CDN 請求，代表本地 vendor 載入失敗，應回到 Console 檢查 `console.error` 訊息。
4. 在 Console 驗證：
   ```js
   window.__mermaid
   window.svgPanZoom
   document.querySelector('#graph-preview svg')
   ```
5. 預期：
   - `window.__mermaid` 為 object。
   - `window.svgPanZoom` 為 function。
   - `#graph-preview svg` 回傳 `SVGSVGElement`。

## Vendor 檔案來源與版本

- `src/amon/ui/static/vendor/mermaid/mermaid.min.js`
  - 來源：`npm pack mermaid@10.9.1` 後取 `dist/mermaid.min.js`
  - 版本：`10.9.1`
- `src/amon/ui/static/vendor/svg-pan-zoom/svg-pan-zoom.min.js`
  - 來源：原本 UI 使用的本地 vendor（對應既有 CDN 版本 `3.6.1`）
  - 版本：`3.6.1`

## `index.html` 以 CDN 載入 Mermaid / svg-pan-zoom 的風險與修正方向

目前狀態：`src/amon/ui/index.html` 直接從 CDN 載入 Mermaid（ESM）與 `svg-pan-zoom`（UMD）。

### 風險點

1. **可用性風險（Availability）**
   - 外網受限、DNS/CDN 故障、企業網路策略會造成 Graph 功能直接失效。

2. **版本漂移風險（Version Drift）**
   - 即使 URL 含版本，仍可能因跨版本行為差異導致 DOM 結構改變，影響 `g.node` 綁定、事件與樣式 class 假設。

3. **供應鏈風險（Supply Chain）**
   - 依賴第三方 CDN 發佈內容；若無額外驗證機制，存在被污染或不可預期變更風險。

4. **偵錯成本上升**
   - 問題受網路/CDN 狀態影響，難以在 CI 或離線環境穩定重現。

### 預期修正方向

1. **改為本地打包與鎖版**
   - 將 Mermaid、svg-pan-zoom 納入前端依賴並由建置流程產出（避免 runtime 直接抓 CDN）。

2. **保留 fallback／降級策略**
   - 若圖形庫未載入，UI 顯示明確錯誤提示與排查指引（不要靜默失敗）。

3. **建立版本相容性檢查**
   - 對 Graph 節點選擇器、狀態 class、點擊行為建立回歸測試，避免升版後無聲壞掉。

4. **環境一致化**
   - CI / 本機 / 驗收環境盡量使用相同資產來源，降低「只在某環境壞掉」的機率。
