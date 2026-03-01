# Graph Debug 手動驗收與排查指南

> 目的：提供 Graph 頁面（Mermaid + svg-pan-zoom）的手動驗收流程、常見失敗排查方式，以及本地 vendor 載入策略的驗證方式。

## 本地 vendor 版本與來源

- `src/amon/ui/static/vendor/mermaid/mermaid.esm.min.mjs`
  - 來源：npm `mermaid@10.9.1` 套件 tarball（`package/dist/mermaid.esm.min.mjs`）。
- `src/amon/ui/static/vendor/svg-pan-zoom/svg-pan-zoom.min.js`
  - 來源：repo 既有 vendor（對應 `svg-pan-zoom@3.6.1`，與 fallback 版本一致）。

## 手動驗收步驟（至少 8 步）

1. **啟動 UI Server**
   - 在 repo root 執行：
     ```bash
     amon ui --port 8000
     ```
   - 確認終端機顯示服務啟動成功，並可存取 `http://localhost:8000`。

2. **開啟 Graph 頁**
   - 進入 `http://localhost:8000`。
   - 從 UI 導航到 Graph 頁（或直接前往 `#/graph`）。

3. **確認 Mermaid 是否載入**
   - 打開 DevTools Console，輸入：
     ```js
     window.__mermaid
     ```
   - 預期：回傳 `object`（不是 `undefined` / `null`）。

4. **確認 svg-pan-zoom 是否載入**
   - 在 Console 輸入：
     ```js
     window.svgPanZoom
     ```
   - 預期：回傳 `function`（不是 `undefined`）。

5. **確認 Graph 是否渲染成功**
   - 在 Console 輸入：
     ```js
     document.querySelector('#graph-preview svg')
     ```
   - 預期：回傳 `SVGSVGElement`，代表 `#graph-preview` 內有 `svg`。

6. **確認節點可點擊（開啟 drawer）**
   - 在圖上點擊任一節點（通常為 `g.node`）。
   - 預期：節點詳細資訊 drawer（側欄）開啟，內容切換到該節點。

7. **確認節點狀態 class 有套用**
   - 在 Elements 面板選取任一 `g.node`，檢查 class。
   - 預期：class 內包含 `node-status--*`（例如 `node-status--running` / `node-status--done` / `node-status--failed`）。

8. **確認增量更新（狀態刷新不閃爍）**
   - 觸發一次 run，讓節點狀態更新。
   - 預期：
     - 節點狀態 class 有更新。
     - 圖面不應整張重建造成明顯閃爍。

9. **補充驗收：縮放/平移不影響點擊**
   - 嘗試滾輪縮放與拖曳平移後，再點擊節點。
   - 預期：縮放/平移正常，節點仍可點擊並開啟 drawer。

10. **確認 Network 不再依賴 jsdelivr（本地 vendor 驗證）**
    - DevTools → Network，清空紀錄後重新整理頁面。
    - 在 Filter 輸入：`jsdelivr`。
    - 預期：
      - 正常情況下，**不會**出現 `mermaid` / `svg-pan-zoom` 的 `cdn.jsdelivr.net` 請求。
      - 僅在本地 vendor 檔案遺失或載入失敗時，才會看到 Mermaid CDN fallback 請求。

## 常見失敗排查

### 1) CDN 被擋或離線，導致 `window.__mermaid` 不存在

**症狀**
- `window.__mermaid === undefined`
- Network/Console 出現 `ERR_BLOCKED_BY_CLIENT`、`net::ERR_INTERNET_DISCONNECTED`、`Failed to load module script`

**排查步驟**
1. DevTools → Network 重新整理頁面。
2. 篩選 `mermaid` / `jsdelivr`，確認回應狀態是否為 `200`。
3. 檢查公司防火牆、代理、AdBlock 是否阻擋 CDN。
4. 若可行，切換可連外網路再重試。

**建議處置**
- 驗收環境先將 `cdn.jsdelivr.net` 納入白名單。
- 以同網段其他機器交叉確認是否為網路策略問題。

### 2) Mermaid `render` 丟錯（如何抓錯誤）

**症狀**
- `window.__mermaid` 存在，但圖未渲染。
- Console 出現 Mermaid parser/render error。

**排查步驟**
1. Console 開啟 **Preserve log**，重新觸發渲染。
2. 搜尋關鍵字：`mermaid`、`parse`、`render`。
3. 暫時掛上全域錯誤監聽，擷取訊息：
   ```js
   window.addEventListener('error', (e) => {
     if (String(e?.message || '').toLowerCase().includes('mermaid')) {
       console.error('[graph-debug] mermaid error:', e.error || e.message);
     }
   });
   ```
4. 檢查輸入的 mermaid 文法（例如未閉合、錯誤箭頭語法、特殊字元未處理）。

### 3) SVG 有出現但沒有 `g.node`（Mermaid 版本差異）

**症狀**
- `document.querySelector('#graph-preview svg')` 有值。
- `document.querySelectorAll('#graph-preview g.node').length === 0`。

**排查步驟**
1. 在 Elements 展開 `#graph-preview svg`，確認實際節點 DOM 結構。
2. 用較寬鬆 selector 檢查（例如 `#graph-preview g`）判斷是否 class 命名改變。
3. 比對目前 Mermaid 版本與既有事件綁定邏輯是否一致。

**處置方向**
- 讓節點選擇器更具相容性（避免只綁 `g.node` 單一 class 假設）。
- 升版 Mermaid 時同步更新回歸測試。

## `index.html` 載入策略（本地優先、CDN fallback）

> 目前 `src/amon/ui/index.html` 採用本地 vendor 優先載入：
> - svg-pan-zoom：先載入本地 `static/vendor/svg-pan-zoom/svg-pan-zoom.min.js`，缺失時才 fallback CDN。
> - Mermaid：先 dynamic import 本地 `static/vendor/mermaid/mermaid.esm.min.mjs`，失敗才 fallback CDN。

### 風險點

1. **可用性風險（Availability）**
   - 外網受限、DNS 異常、CDN 故障時，Graph 功能可能直接失效。

2. **版本漂移風險（Version Drift）**
   - 即使固定版本，升級或跨環境仍可能造成 DOM 結構改變，影響 `g.node` 選擇與事件綁定。

3. **供應鏈風險（Supply Chain）**
   - 前端關鍵依賴由第三方 CDN 提供，需承擔來源可用性與內容一致性風險。

4. **除錯與重現成本上升**
   - 問題可能只在特定網路條件出現，導致本機、CI、驗收環境不一致。

### 預期修正方向

1. **改為本地資產或建置產物鎖版**
   - Mermaid / svg-pan-zoom 改由 repo 內建置流程提供，避免 runtime 直接依賴 CDN。

2. **保留清楚的降級訊息**
   - 若圖形庫載入失敗，UI 顯示可操作的錯誤訊息與排查步驟，不可靜默失敗。

3. **建立相容性回歸測試**
   - 針對 `#graph-preview svg`、節點點擊、`node-status--*` class 套用建立穩定測試。

4. **統一環境依賴來源**
   - 本機/CI/驗收盡量使用一致資產來源，降低「某環境才壞」的風險。
