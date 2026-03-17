# Web Design Principles（前端網頁設計原則）

本文件整理常用的前端網頁設計技巧，用於補強視覺層級、資訊架構與互動效率。

## 視覺層級（Visual Hierarchy）
- **尺寸對比**：主標 > 副標 > 內文，使用明顯的字級差異建立閱讀順序。
- **色彩對比**：用高對比強化重點，但避免過度飽和造成疲勞。
- **留白與節奏**：區塊間距大於內距，讓群組邊界清楚。
- **對齊與網格**：一致的對齊能讓內容更容易掃描。

## 認知與可用性（Cognitive Load）
- **Chunking（分塊）**：將資訊拆成小群組，降低記憶負擔。
- **Choice Overload**：過多選項會降低決策效率，必要時先分組或預設選擇。
- **Fitts’s Law**：常用操作應該更大、靠近主要視覺區域。

## 視覺一致性
- **一致的視覺語言**：按鈕、卡片、輸入欄位需共享同一套 Token。
- **語意化顏色**：成功/警告/危險狀態需用固定語意色。

## 多步驟體驗與感知原則
- **Journey / Flow 先行**：多步驟 UX 先畫 user journey / user flow，再進入高保真。
- **狀態可見性**：使用者需要知道目前位置、已完成內容與下一步。
- **Gestalt**：以 proximity、similarity、figure-ground、continuation 建立掃描路徑與群組感。
- 詳細規則與檢查方式見 `journey-flow-gestalt.md`。

## 互動回饋
- **立即回饋**：點擊、hover、focus 必須有明顯視覺回饋。
- **延遲容忍**：超過 400ms 需使用 skeleton 或進度提示。

## 參考來源
- Laws of UX（多個設計/認知法則）：https://lawsofux.com/
- Nielsen Norman Group: 10 Usability Heuristics：https://www.nngroup.com/articles/ten-usability-heuristics/
