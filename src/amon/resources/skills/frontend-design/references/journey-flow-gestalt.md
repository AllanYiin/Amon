# Journey / Flow / Gestalt 實作原則

這份參考文件把 NNG 的 UX map 實務與 Gestalt 感知原則，轉成前端設計與程式碼交付時可操作的規則。

## 1. 先選對可視化類型

- `Journey map`：描述單一角色在跨時間、跨接觸點的端到端體驗，適合 onboarding、checkout、客服支援等長流程。
- `User flow`：描述使用者在產品內完成單一任務的理想路徑、分支與決策點，適合任務流與資訊架構。
- `Wireflow`：把 user flow 與低保真畫面結合，適合需要同步談「順序」與「畫面骨架」的工作。

若是多步驟、跨頁、跨狀態的 UI，至少要交付 `journey map` 或 `user flow`，不要只貼高保真畫面。

## 2. NNG 導出的 journey / flow 可視化規則

### 結構規則

- 固定單一 `persona / actor`、單一 `scenario`、單一 `goal`，避免把不同角色與目標揉在一起。
- 以時間順序呈現 `steps / phases / touchpoints / screens`，讓人一眼看出前後關係。
- 每一步至少交代：
  - 使用者在做什麼
  - 使用者在想什麼或感受什麼
  - 系統目前回饋了什麼
  - 哪裡出現 pain point 或 opportunity
- 若流程牽涉後台或人工服務，將前台（frontstage）與後台（backstage）拆開，而不是全部塞在同一層。

### fidelity 規則

- 早期探索優先低保真，先對齊流程與內容，避免太早被視覺細節綁死。
- 一旦要討論互動細節，補成 wireflow 或互動式 UX map，而不是只靠靜態截圖。
- 關鍵流程不要用 lorem ipsum 或模糊框框帶過；標示真實欄位、關鍵動作、系統狀態與文案。

### 可用性規則

- 多步驟流程必須顯示目前位置、已完成與下一步，對應 NNG 的 `Visibility of System Status`。
- 流程圖中的主要路徑應比支線更醒目；錯誤、回退、替代路徑要明確標示。
- 圖與畫面都要能回答：「如果使用者卡在這裡，會知道現在在哪、下一步是什麼、如何返回嗎？」

## 3. Gestalt 感知原則轉成前端規則

### Proximity / Common Region

- 用一致的間距、容器、底色或框線把同一群資訊包成一個視覺單位。
- 區塊外距要大於內距，讓使用者能明確分辨群組邊界。
- 表單、filters、summary、CTA 不要混成單一大片。

### Similarity

- 相同行為與語意的元件，要共享 token、形狀、尺寸與互動回饋。
- 不同層級的 CTA 必須有穩定變體，不要每個按鈕都長得不一樣。
- icon + label、badge、status chip、navigation item 都應遵守同一套視覺語法。

### Figure-Ground

- 背景、表面、文字與重點操作要有足夠層次，避免內容沉在背景裡。
- 主要 CTA、當前步驟、錯誤訊息要在視覺上從背景浮出來。
- token 層至少區分 `background / surface / text / border / primary`。

### Continuation

- 視線路徑要順著流程前進，例如 stepper、timeline、connector、箭頭、編號順序。
- 主要內容應沿單一閱讀軸排列；不要讓使用者在畫面中來回跳躍找下一步。
- 橫向 stepper 與縱向摘要要互相對齊，不要製造視覺斷點。

### Closure / Common Fate

- 這兩項通常需要人工目視確認，無法只靠靜態字串掃描保證正確。
- 若用動畫暗示群組或流程，需確認 `prefers-reduced-motion` 下仍能理解。

## 4. 機器可檢查的代理指標

下列項目可由 `scripts/audit_frontend_principles.py` 做可復現檢查：

- 是否有 `persona / scenario / steps` 的 journey 或 flow 文件
- 是否有 `thinking / feeling / pain point / opportunity` 類型欄位
- 是否有 `progress / aria-current / completed / next step` 等系統狀態訊號
- 是否有 `gap / spacing / section / fieldset` 等 proximity/common region 代理訊號
- 是否有 `tokens / variants / semantic color` 等 similarity 代理訊號
- 是否有 `background / surface / text / contrast` 等 figure-ground 代理訊號
- 是否有 `stepper / timeline / connector / ordered sequence` 等 continuation 代理訊號

## 5. 建議交付契約

做多步驟 UI 時，交付物至少應包含：

1. `journey` 或 `flow` 文件
2. 畫面或元件程式碼
3. 一次 audit 結果

建議命令：

```bash
python skills/frontend-design/scripts/audit_frontend_principles.py <workspace>
python skills/frontend-design/scripts/audit_frontend_principles.py <workspace> --format json
```

## 來源

- NNG, `Journey Mapping` PDF: [https://media.nngroup.com/media/reports/free/Journey_Mapping.pdf](https://media.nngroup.com/media/reports/free/Journey_Mapping.pdf)
- NNG, `UX Mapping Glossary` PDF: [https://media.nngroup.com/media/reports/free/UxMappingGlossary.pdf](https://media.nngroup.com/media/reports/free/UxMappingGlossary.pdf)
- NNG, `Interactive UX Maps: A Practice Guide` PDF: [https://media.nngroup.com/media/reports/free/Interactive_UX_Maps.pdf](https://media.nngroup.com/media/reports/free/Interactive_UX_Maps.pdf)
- NNG, `Visibility of System Status` PDF: [https://media.nngroup.com/media/reports/free/VisibilityOfSystemStatus.pdf](https://media.nngroup.com/media/reports/free/VisibilityOfSystemStatus.pdf)
- Interaction Design Foundation, `What is Perception and Why is it Important?`: [https://www.interaction-design.org/literature/topics/perception](https://www.interaction-design.org/literature/topics/perception)
- Interaction Design Foundation, `Gestalt Principles`: [https://www.interaction-design.org/literature/topics/gestalt-principles](https://www.interaction-design.org/literature/topics/gestalt-principles)
- Wagemans et al., `A Century of Gestalt Psychology in Visual Perception`: [https://pmc.ncbi.nlm.nih.gov/articles/PMC3842470/](https://pmc.ncbi.nlm.nih.gov/articles/PMC3842470/)
