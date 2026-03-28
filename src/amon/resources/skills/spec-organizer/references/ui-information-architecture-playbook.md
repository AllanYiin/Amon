# UI Information Architecture Playbook

這份文件用來把「功能清單」收斂成可執行的 UI 規格，避免規格整理最後只產出 stacked cards 或 feature parking lot。

## 1. 先把功能清單翻成任務模型

很多 stacked UI 的根因不是 UI 技術太弱，而是規格只寫了功能，沒寫任務主軸。

先強制整理成：

| 層級 | 定義 | 例子 |
|---|---|---|
| 唯一主目標 | 使用者進這一頁最重要、當下就要完成的事 | 提交分享連結並確認是否可送件 |
| 次目標 | 完成主任務前後會需要，但不是第一眼唯一焦點 | 查看檢核結果 |
| 低頻目標 | 可能需要查，但不應常駐 | 閱讀評分規則與格式說明 |
| 罕見目標 | 只有特定情況才需要 | 上傳 PDF / 截圖補件 |

如果這張表寫不出來，代表需求仍停在功能 inventory，不能直接進 UI 規格。

## 2. 用 state model 決定 reveal / hide

資訊是否可見，優先看使用者目前在哪個 state，而不是看資訊本身是否存在。

常見狀態：

- `empty`
- `drafting`
- `validating`
- `resolved`
- `blocked`
- `submitted`

每個 state 都至少要回答：

- 使用者此刻目標是什麼
- 哪些區塊必顯
- 哪些區塊必須隱藏
- 此刻唯一主 CTA 是什麼
- 什麼事件讓使用者離開這個 state

## 3. 每個資訊項目都要分類

分類只允許以下幾種：

- `action-critical`
- `decision-supporting`
- `status-feedback`
- `reference`
- `exception-handling`
- `audit/history`

沒有分類的資訊項目，不能直接進版面。

## 4. 先產出資訊架構表，再產出 UI

至少要整理成這張表：

| 資訊項目 | 使用頻率 | 是否首屏必須 | 所屬任務階段 | 顯示條件 | 建議容器 | 是否可收合 |
|---|---|---|---|---|---|---|
|  | 高 / 中 / 低 | 是 / 否 | empty / drafting / validating / resolved / blocked / submitted |  | inline / panel / sticky footer / accordion / drawer / modal / tab | 是 / 否 |

這張表的用途不是好看，而是強迫規格先做 reveal / hide 判斷。

## 5. Progressive disclosure 要寫成硬規則

預設規則：

- 首屏最多只允許 1 個主操作區、1 個狀態區、1 個次要摘要
- `reference` 類資訊預設收合
- `exception-handling` 只在錯誤或例外 state 顯示
- 進階設定放進 accordion / drawer / modal
- 相同任務流中的說明文字優先內嵌在元件旁
- 單頁最多 3 個主要視覺群組，超過就要合併或延後揭露

## 6. 什麼情況該拆成 step flow

若符合以下兩項以上，優先寫成 tabs / wizard / step navigation：

- 任務有明確先後順序
- 後一步高度依賴前一步輸出
- 使用者一次只需要看局部資訊
- 例外處理只在部分節點出現
- 首屏超過 3 個主要群組

## 7. Reviewer 提問

在審規格時至少問：

- 這一頁唯一最重要的任務是什麼
- 哪些內容只是 `reference`
- 哪些內容其實只該出現在 `blocked` 或 `resolved`
- 右欄是否只是因為有空間才存在
- 如果只能保留 3 個區塊，會保留哪 3 個
- 是否有大型說明卡其實應該改成 inline helper

## 來源概念

- Task analysis：先拆使用者任務與子任務，再檢查功能是否真的支援目標。
- State-driven UI：用有限狀態與轉移控制畫面顯示，避免不可能狀態同時存在。
- Progressive disclosure：讓低頻與進階內容後退，不與當前主任務爭奪注意力。
