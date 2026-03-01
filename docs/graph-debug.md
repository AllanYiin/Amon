# Graph Debug 手動驗收與排查指南

> 目的：提供 Graph 頁面（Mermaid + svg-pan-zoom）的手動驗收流程、常見失敗排查方式，以及 `index.html` 目前使用 CDN 載入的風險與修正方向。

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

## 常見失敗排查

### 分支對照（Graph 頁 UI 訊息）

| 分支 | 觸發條件 | UI 文案 | 建議排查 |
| --- | --- | --- | --- |
| A | `graph_mermaid` 為空或缺失 | `此 Run 尚無流程圖資料` + `請先查看下方 graph-code 區塊是否有內容。` | 確認該 Run 是否真的有產生 graph payload；比對 graph-code 與後端回傳欄位。 |
| B | `graph_mermaid` 有值，但 `window.__mermaid` 不存在/不可 render | `Mermaid 未載入（可能離線或資源被擋）` + `請嘗試重新整理頁面後再試一次。` | 檢查 CDN/網路阻擋、Console 與 Network 錯誤，並先重新整理。 |
| C | `window.__mermaid.render(...)` throw error | `流程圖渲染失敗` + `錯誤摘要：<error.message>` | 驗證 mermaid 文法，從 Console 追蹤 parser/render error。 |
| D | SVG 渲染成功但找不到 `g.node` 或無法綁定節點 | `流程圖已渲染但無法識別節點` + `可能是 Mermaid 版本差異，請比對 g.node 結構。` | 檢查 SVG 結構與 class 命名，確認 Mermaid 版本與 selector 相容性。 |

> 設計重點：即使進入 B/C/D，Node 清單與 Node drawer 仍可操作，使用者可以先從清單點擊節點查看 detail。

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
- Graph UI 會顯示「Mermaid 未載入（可能離線或資源被擋）」並提供重新整理按鈕。

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

**快速重現（DoD 建議）**
- 可在測試 payload 中提供非法語法：
  ```text
  flowchart TD
  A-->
  ```
- 預期 Graph UI 顯示「流程圖渲染失敗」與錯誤摘要。

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
- Graph UI 會保留已渲染 SVG，並在上方顯示「流程圖已渲染但無法識別節點」警示。

## `index.html` 使用 CDN 載入 Mermaid / svg-pan-zoom 的風險點與預期修正方向

> 目前 `src/amon/ui/index.html` 透過 CDN 載入 Mermaid 與 svg-pan-zoom。

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
