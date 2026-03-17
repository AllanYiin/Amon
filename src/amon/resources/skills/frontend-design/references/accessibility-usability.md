# Accessibility & Usability Checklist（可用性與無障礙）

## 目標
- 以 WCAG A/AA 為最低基準。
- 所有互動元件需完整支援鍵盤操作。
- 可用性檢查要同時涵蓋心智模型、一致性、回饋、錯誤預防與復原。

## 核心清單
1. **可感知**
   - 文本對比度足夠（一般文字 ≥ 4.5:1）。
   - 不用顏色單獨傳遞資訊。
   - 重要資訊不只靠圖示。

2. **可操作**
   - 所有功能皆可用鍵盤完成。
   - Focus 可見且清楚。
   - 互動元件最小點擊區域 ≥ 44px。

3. **可理解**
   - 表單錯誤有明確提示與修正方式。
   - 導覽結構符合常見慣例。

4. **穩健性**
   - 使用語意 HTML（button、nav、main）。
   - 需要時補 ARIA，但不濫用。

5. **符合使用者心智模型**
   - 優先使用真實世界語言與常見 UI 慣例。
   - 導覽、表單、狀態名稱不要讓使用者重新學一次產品語法。
   - 若是多步驟流程，畫面中的名詞與流程圖/文件中的名詞必須一致。

6. **一致性與簡化**
   - 同一語意的操作保持相同 label、位置、色彩與互動模式。
   - 優先讓使用者辨識，而不是要求記憶上一頁或隱藏規則。
   - 每個畫面只保留能支持當前任務的資訊與操作。

7. **回饋與錯誤復原**
   - 成功、失敗、loading、empty、permission denied 都要有明確回饋。
   - 錯誤訊息要說明發生什麼、怎麼修、下一步是什麼。
   - 高風險操作需有預防機制與復原路徑，例如 confirm、undo、retry、back。

8. **驗證方式**
   - 先做低保真原型，再做高保真。
   - 至少用 1 位以上真實或代理使用者做 task walkthrough。
   - 交付前用 keyboard-only、縮窄視窗、空資料、錯誤資料各跑一輪。

## 參考來源
- The A11Y Project Checklist：https://www.a11yproject.com/checklist/
- WCAG（A/AA 等級概念）：https://www.w3.org/WAI/standards-guidelines/wcag/
- Nielsen Norman Group: 10 Usability Heuristics：https://www.nngroup.com/articles/ten-usability-heuristics/
- StartCompany, `使用者介面設計`：[https://startcompany.tw/%E4%BD%BF%E7%94%A8%E8%80%85%E4%BB%8B%E9%9D%A2%E8%A8%AD%E8%A8%88/](https://startcompany.tw/%E4%BD%BF%E7%94%A8%E8%80%85%E4%BB%8B%E9%9D%A2%E8%A8%AD%E8%A8%88/)
- Medium, `UX 黃金法則：10 大易用性原則`：[https://medium.com/@seeuagain/ux-%E9%BB%83%E9%87%91%E6%B3%95%E5%89%87-10-%E5%A4%A7%E6%98%93%E7%94%A8%E6%80%A7%E5%8E%9F%E5%89%87-%E4%BD%A0%E5%81%9A%E5%88%B0%E4%BA%86%E5%B9%BE%E9%A0%85-091c4dcef76d](https://medium.com/@seeuagain/ux-%E9%BB%83%E9%87%91%E6%B3%95%E5%89%87-10-%E5%A4%A7%E6%98%93%E7%94%A8%E6%80%A7%E5%8E%9F%E5%89%87-%E4%BD%A0%E5%81%9A%E5%88%B0%E4%BA%86%E5%B9%BE%E9%A0%85-091c4dcef76d)
