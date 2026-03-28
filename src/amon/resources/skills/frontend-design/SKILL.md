---
name: frontend-design
description: 在使用者要設計網站、Web App 或元件介面時使用。常見觸發像「做 landing page」「設計 dashboard」「規劃 component UI」。輸出可上線介面與設計系統；不取代產品策略或純品牌研究。
version: 2026.3.26
homepage: https://github.com/AllanYiin/skills/tree/main/skills/frontend-design
license: MIT
metadata: {"author":"Allan Yiin","language":"zh-TW","category":"design","short-description":"前端 UI 設計、視覺系統與可上線實作工作流程"}
---

# Frontend Design Skill

## Purpose

這個 skill 用來把模糊的網站、Web App 或元件需求，轉成可上線的前端介面與設計系統實作。核心不是只把畫面做漂亮，而是先定義設計 tokens、互動狀態、流程可視化、資訊優先級與可重用規範，再落成前端程式碼。若是工作台型產品，嚴格禁止 stacked UI / stacked cards 疊首頁；必須先定義唯一主任務，並讓該功能盡量佔據最大、最中央、最先被看的畫面區域。

## Scope

### In scope
- 網站、Web App、dashboard、landing page、admin panel、component library 與 design system 的 UI 設計與實作。
- 從設計方向、tokens、components、page layout 到互動狀態與 accessibility 的整體規劃。
- 多步驟體驗中的 journey map、user flow、wireflow 與 Gestalt 原則落地。
- 以 React、Vue、Svelte、HTML/CSS/Tailwind 等常見 Web 技術完成前端交付。

### Out of scope
- 純後端 API、演算法、資料處理或非視覺性的程式任務。
- 純品牌策略、產品定位或沒有 UI 輸出的設計討論。
- 只要求修單一小 bug、調一個 CSS 值且不涉及系統性 UI 改善的任務。

## Primary Use Cases

1. 從需求直接產出可上線頁面或元件。
Trigger examples: 「做 landing page」「設計 dashboard」「規劃 component UI」。
Expected result: 交付 tokens、components、page layout 與對應前端程式碼，而不是只給視覺形容詞。

2. 建立或整理設計系統。
Trigger examples: 「整理一套 design system」「把元件規範化」「做可重用 UI guideline」。
Expected result: 交付 tokens、shared components、guideline docs 與 reusable patterns。

3. 處理多步驟 UX 流程。
Trigger examples: 「設計 onboarding flow」「把 checkout 流程整理清楚」「規劃 setup wizard」。
Expected result: 先產出 journey map / user flow / wireflow，再進入高保真 UI 實作。

## Workflow Overview

1. 先定義任務目標、使用者、技術棧、美學方向，以及唯一 primary task。
2. 建立設計 tokens 與狀態規範，避免任意硬編碼。
3. 先做 task model、state model、資訊分類、資訊架構表與揭露策略，再規劃 components 與 page layouts；必要時先做 journey/flow。
4. 補齊 loading、empty、error、focus、responsive、accessibility 與 visibility rules。
5. 用 deterministic audit 與 anti-pattern checklist 自檢。

詳細流程看 `references/implementation-workflow.md`。

## Routing Boundaries

- Neighboring skills / workflows:
  - `spec-organizer`: 需求還沒成形、需要先整理成可開發 spec。
  - `slide-content-planner` / `pptx-maker`: 目標是簡報而不是 Web UI。
  - `technical-documentation-writer`: 重點是文件，不是前端介面。
- Negative triggers:
  - 「幫我修 backend API」
  - 「只要演算法，不用管 UI」
  - 「幫我寫品牌定位」
- Handoff rule: 若任務核心不是介面或前端實作，就不要硬用 UI 技巧包裝不相干問題。

## Success Criteria

### Quantitative
- 所有互動元件都有 default / hover / active / focus / disabled 狀態。
- 響應式至少覆蓋 mobile、tablet、desktop 三個 viewport。
- 如為多步驟流程，必有 journey map / user flow / wireflow 其中之一。
- 如為 workspace / dashboard / review tool，首屏必須有明確的 task model、state model、資訊架構表與 visibility plan。

### Qualitative
- 輸出要能直接做，不是只剩風格形容詞。
- 視覺方向明確且不落入 generic AI slop。
- tokens、components、states 與 guideline 彼此一致。
- 若是 dashboard、workspace、viewer、editor、review tool 或 compare screen，必須只聚焦一個 primary task；禁止用 stacked UI 延後使用者接觸真正主功能。
- 首屏只保留完成當前任務所需的主要群組；reference、規則、補充說明與低頻控制項必須延後揭露。

## Trigger Patterns

**應觸發**
- 「做 landing page」
- 「設計 dashboard」
- 「規劃 component UI」
- 「整理 design system」
- 「把這個 mockup 轉成前端頁面」

**不應觸發**
- 「幫我修 API timeout」
- 「幫我做資料清洗腳本」
- 「幫我寫品牌定位」

## Testing Plan

### Triggering tests
- Should trigger:
  - "build a website/app/component"
  - "create a dashboard/landing page"
  - "design a UI for..."
  - "make it modern/clean/premium"
- Should NOT trigger:
  - "幫我修 API timeout"
  - "幫我做資料清洗腳本"
  - "幫我寫品牌定位"

### Functional tests
- 若有 reusable UI，應同時交付 guideline docs。
- 若有 multi-step UX，必須先外顯化 flow artifact。
- 交付前要跑 `audit_frontend_principles.py` 或等價檢查。

## Non-Negotiables

1. 先做 tokens，再做 components；不要直接硬編碼顏色、間距、陰影與圓角。
2. 一個畫面先定義一個 primary task；嚴格禁止 stacked UI / stacked cards 疊首頁，主工作區必須佔據主舞台與最大化畫面區域。
3. 在畫 layout 前，先產出 task model、state model、資訊分類、資訊架構表與 disclosure plan；沒有這些前置物就不要直接堆 card。
4. 每個資訊項目都要標記為 `action-critical`、`decision-supporting`、`status-feedback`、`reference`、`exception-handling` 或 `audit/history` 其中之一。
5. task model 不能只寫功能名稱；至少拆成唯一主目標、次目標、低頻目標、罕見目標。
6. state model 不能只列 state 名稱；至少要為每個 state 定義進入條件、必顯資訊、隱藏資訊、主 CTA 與離開條件。
7. 先用資訊架構表決定 reveal / hide，再決定 layout；資訊架構表至少要有：資訊項目、使用頻率、是否首屏必須、所屬任務階段、顯示條件、建議容器、是否可收合。
8. 依 state 決定可見性：reference 預設 on-demand、exception 只在對應狀態出現、右欄只在明確有助於當前任務時才常駐。
9. 首屏預設只允許 1 個主操作區、1 個狀態區、1 個次要摘要；整體不得超過 2-3 個主要視覺群組，且只能有 1 個主 CTA。
10. 相同任務流中的說明文字優先內嵌在元件旁，不要獨立做成大型說明卡。
11. 多步驟 UX 必須先外顯化成 journey map、user flow 或 wireflow。
12. Reusable UI 必須附 guideline docs，不可只交程式碼。
13. Accessibility、loading、empty、error 與 focus state 都是交付內容，不是加分項。
14. Tailwind 只能走 build-time integration，不要用 CDN 當正式方案。
15. 交付前要做 anti-pattern scan 與 deterministic audit。

細節看：
- `references/core-principles.md`
- `references/common-pitfalls.md`
- `references/quality-checklist.md`

## Skill Architecture

- `SKILL.md`
  - 路由邊界、核心規則摘要、交付標準與導航。
- `scripts/audit_frontend_principles.py`
  - Journey/flow、Gestalt、guideline 與 task hierarchy 的 deterministic audit。
- `examples/css/`
  - `tokens.css`: 設計 token 系統。
  - `components.css`: 可重用元件樣式範例。
- `examples/typescript/`
  - `design-tokens.ts`: type-safe token 定義。
  - `theme-provider.tsx`: theme 管理。
  - `sample-components.tsx`: 元件範例。
  - `utils.ts`: 共用輔助。
- `templates/`
  - `globals.css`: 全域樣式模板。
  - `tailwind.config.js`: Tailwind 設定模板。

## Reference Navigation

只讀和當前任務直接相關的 reference，不要全部一起載入。

- `references/core-principles.md`
  - tokens-first、Tailwind build-time、journey/flow、Gestalt、workbench hierarchy、單一主任務與反 stacked UI 規則、guideline artifacts。
- `references/information-priority-playbook.md`
  - task model、state model、資訊分類、資訊架構表、progressive disclosure、首屏群組上限與 anti-stacked workbench 規則。
- `references/implementation-workflow.md`
  - 從分析、token 定義、component/page 組裝到 QA 的完整 phase-by-phase 流程。
- `references/design-direction-templates.md`
  - Minimal Premium SaaS、Bold Editorial、Soft & Organic、Dark Neon、Playful & Colorful 的方向模板。
- `references/prompting-playbook.md`
  - master prompt、token/component/page/review prompts 與 quick-start example。
- `references/common-pitfalls.md`
  - 常見前端設計失敗型態與修法。
- `references/quality-checklist.md`
  - 輸出品質標準、驗收 checklist、tips for excellence。
- `references/advanced-techniques.md`
  - fluid typography、advanced color systems、skeleton loading、motion patterns。
- `references/frontend-resources.md`
  - 技能內建參考與外部資源索引。

既有深度參考：
- `references/web-design-principles.md`
- `references/accessibility-usability.md`
- `references/responsive-typography.md`
- `references/journey-flow-gestalt.md`
- `references/design-guideline-authoring.md`

## Delivery Rule

回覆或實作時，優先遵守：
- 用祈使句與可執行規格溝通，不要只給空泛審美詞。
- 能用現有 examples / templates / references 解決，就不要在 `SKILL.md` 重新展開長篇教學。
- 若任務是工作台型 UI，先保護唯一主任務與主舞台，再處理裝飾、摘要卡片或次要資訊。
- 若任務包含很多功能，先做資訊架構收斂，把 feature inventory 壓成 visibility plan；不要把每個需求都停進一張卡片。
- 若任務只是局部小修，仍要保護設計系統一致性，但不要擅自重做整個頁面。
