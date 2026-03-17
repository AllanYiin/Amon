# UI Guideline Authoring

這份文件把 UI guideline 從「漂亮的設計文件」收斂成「設計、PM、工程都能用的交付契約」。

## 1. Guideline 的目的

- guideline 不是作品集頁面，而是跨角色溝通與落地實作的說明書。
- 它要回答的不只是「長怎樣」，還包括：
  - 什麼情境該用
  - 什麼情境不該用
  - 尺寸、間距、狀態、互動、文案、資產怎麼定義
  - 工程該如何實作與驗證

## 2. 何時必須交付 guideline

下列任務不應只交 JSX/CSS：

- 元件庫
- design system
- 可重用的表單元件、導航元件、卡片、modal、stepper
- 需要多人協作維護的中大型 UI

若只是一次性的單頁原型，可以簡化，但仍應保留 state 與規格說明。

## 3. 建議結構：由大到小寫

每個關鍵元件或模式，至少整理以下段落：

1. `Usage`
- 解釋用途、適用情境、非適用情境
- 說明與相近元件的差異

2. `Layout`
- 容器、間距、對齊、密度、斷點行為
- 與周邊元件的組合方式

3. `Anatomy`
- 元件構成：icon、label、helper text、prefix/suffix、actions、media
- 哪些部分是必要，哪些是可選

4. `States & Spec`
- default / hover / focus / active / disabled / loading / error / empty
- 尺寸、最小點擊區、padding、radius、color token、line-height

5. `Interaction`
- 點擊、鍵盤、手勢、動畫、焦點移動、狀態切換
- 成功、失敗、取消、返回、retry、undo 等復原路徑

6. `Content / Copy`
- CTA 命名原則
- 錯誤訊息與空狀態文案
- 避免模糊詞，例如 `OK`、`Submit`、`Something went wrong`

7. `Asset / Implementation`
- token 對應
- icon / illustration / image 規範
- 工程注意事項與範例

## 4. Style guideline 與 component guideline 分開

- `Style guideline`：字體、色彩、間距、圖像風格、motion、品牌語氣
- `Component guideline`：按鈕、表單、卡片、表格、modal、stepper 等元件規範

不要把品牌風格與元件實作細節混成一坨，否則工程很難直接採用。

## 5. 寫法原則

- 優先用「使用規則 + 反例」而不是只放漂漂亮亮的圖。
- 每段都盡量能對應到工程上的具體決策。
- 優先列出最常用、最易錯、最會造成不一致的元件。
- guideline 應和真實程式碼、token、狀態一起更新，而不是脫節的靜態文件。

## 6. 可機器檢查的最低結構

`audit_frontend_principles.py` 可以在需要時用 `--require-guideline-docs` 檢查：

- 是否存在 guideline / spec 類型文件
- 是否包含 `Usage`
- 是否包含 `Layout`
- 是否包含 `Anatomy`
- 是否包含 `States` 或 `Spec`
- 是否包含 `Interaction`
- 是否包含 `Content` 或 `Asset`

## 來源

- Huang Rui-Lin, `How to write a UI Design Guideline`: [https://huangruilin.tw/2021/09/03/how-to-write-a-uidesign-guideline/](https://huangruilin.tw/2021/09/03/how-to-write-a-uidesign-guideline/)
- pbakaus, `impeccable` frontend design skill and references: [https://github.com/pbakaus/impeccable](https://github.com/pbakaus/impeccable)
