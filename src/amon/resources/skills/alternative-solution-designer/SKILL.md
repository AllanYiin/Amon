---
name: alternative-solution-designer
description: 當使用者要替代解法、不同思路、更簡單或更穩定做法時使用。將現有方案重構成結構問題，提出多條可落地方案與最低摩擦解。
version: 2026.3.9
metadata:
  author: Allan Yiin
  language: zh-TW
  category: problem-solving
  short-description: 重構問題、比較替代路線，並產出最低摩擦可行方案指引
---

# Alternative Solution Designer

## Purpose

這個 skill 的工作不是把現有方案修得更漂亮，而是重新定義問題，找出更簡單、更穩定、更低成本，或思維路線完全不同但仍可落地的替代作法。

它會先挑戰前提，再把問題拆成結構、模組、限制與決策層次，最後輸出可比較、可評估、可試行的替代方案，而不是抽象腦力激盪。

## Scope

### In scope
- 使用者已提供或可從上下文推得出問題描述、目前解法、限制條件。
- 使用者明確表示不想只優化原解，而是想找不同路線、降複雜度、降成本、降風險或提高穩定性。
- 需要將問題抽象化、找類比、鬆綁假設、模組化拆解，並產出多條方案與 trade-off。
- 需要一條「幾乎不動系統，只改流程或介面」的最低摩擦解。

### Out of scope
- 單純要修 bug、補 feature、調參、重構程式碼，但沒有要求替代解法。
- 已經選定方向，只想直接寫技術 spec、UI 設計或實作程式碼。
- 純發想型腦暴，沒有問題、現況或限制，導致方案無法評估。
- 僅要求美化文案、簡報、設計稿，沒有結構性問題重構需求。

## Primary use cases

1) **現有方案太複雜或太脆弱**
- Trigger examples: "這套流程靠 OCR + LLM + 人工校對，越修越複雜，有沒有更簡單方案？", "我不要再優化這條 pipeline 了，想換思路。"
- Expected result: 找出真正瓶頸、重分類問題結構，提出至少 3 條不同類型替代方案與 1 條最低摩擦解。

2) **團隊卡在單一技術路線**
- Trigger examples: "我們現在全押 agent，但失敗率很高，有沒有不用 agent 的作法？", "可不可以用規則或流程重排取代模型？"
- Expected result: 指出哪些前提其實不是必要，列出成熟技術或非模型解法，並比較成本、穩定性與導入風險。

3) **限制很硬，只能小改**
- Trigger examples: "不准大改系統，只能改 UI 或流程，怎麼改善？", "我只想先用最低摩擦方式止血。"
- Expected result: 提出不動核心架構的替代方案，優先從介面、人工輔助、流程順序、驗證關卡切入。

## Workflow overview

1. 讀取現有對話與檔案，補齊問題描述、目前解法、限制條件、成功標準。
2. 用一句話重構問題本質，指出真正難點。
3. 把問題抽象成結構模型，說明典型解法輪廓。
4. 找至少 2 個他域同構案例，說明怎麼借用。
5. 挖出隱含假設與可放寬限制，推導新可能。
6. 將流程模組化，判斷哪些可重排、替換、刪除。
7. 主動補充成熟技術或非技術手段，標註成熟度。
8. 生成至少 3 條不同思維類型的替代解法，再補 1 條最低摩擦解。
9. 最後檢查內容是否具體、可評估、可落地，並修正任何錯誤前提。

## Communication notes

- User vocabulary: 替代解法、換思路、不要只優化原解、更簡單、更穩、限制條件、最低摩擦解、可落地。
- Avoid jargon: 把「同構」說成「結構相似」，把「eventual consistency」說成「允許延後一致」，把「human-in-the-loop」說成「半自動加人工確認」。
- Least-surprise rule: 預設要直接指出前提錯誤，但不能只否定；每次質疑都要附上具體替代方式。
- Output rule: 不要只給一個答案；至少 3 條不同思維類型方案，且每條都要有作法、優勢、代價、風險。
- Tone rule: 務實、條列、可執行；不要空泛稱讚，也不要把抽象創意包裝成可行方案。

## Routing boundaries

- Neighboring skills / workflows:
  - `spec-organizer`: 當使用者已選定替代方向，接下來要整理成技術 spec、白話 spec 或開發分期時切換。
  - `frontend-design`: 當最佳方案主要是 UI / UX 改版，且使用者要直接產出介面設計與前端實作時切換。
  - `vibe-coding-development-guidelines`: 當使用者已選方案，接下來要做跨平台、一鍵啟動或可交付應用時切換。
  - `skill-creator-advanced`: 當問題本身是在建立、修改、測試或發布 skill，而不是替代解法分析時切換。
- Negative triggers:
  - "幫我直接修這個 bug"
  - "請直接寫規格 / 寫程式 / 做設計稿"
  - "幫我優化目前 SQL / prompt / API latency"
  - "幫我發想名稱、標語、活動點子"
- Handoff rule: 如果替代路線已收斂，只差規格化或實作，明確結束本 skill 的分析階段，交棒給對應 skill，不要繼續重複替代方案討論。

## Language coverage

- Primary language(s): 繁體中文。
- Mixed-language trigger phrases: alternative approach、workaround、fallback design、no-LLM、rule-based、human-in-the-loop、simpler architecture、trade-off。
- Locale-specific wording risks:
  - 「替代方案」有時只是備援方案，不一定是重構思路；若語意不清，要先辨識使用者是要 emergency fallback 還是不同主方案。
  - 「最小改動」有時只是要 hotfix，不一定需要本 skill；若只是小修正而非結構性替代，應避免 over-trigger。

## Success criteria

### Quantitative
- Trigger accuracy: 至少 90% 的明確替代解法查詢能觸發。
- Section completeness: 100% 包含 8 個核心段落與最低摩擦解。
- Alternative diversity: 每次至少 3 條不同思維類型方案，不可只是同一方案的小變體。
- Tool calls: 在一般案例下維持精簡；若涉及新技術、近期工具或限制條件可能已變動，先做必要網路查核再回答。

### Qualitative
- 能清楚指出「真正難的不是什麼，而是什麼」。
- 能拆出隱含假設，而不是沿用使用者原本框架。
- 每條方案都可執行、可評估、可落地，不流於概念口號。
- 有一條低摩擦方案能讓使用者先止血，再決定是否重構。

## Instructions

使用 `references/output-template.md` 的段落順序作為預設輸出骨架；需要判斷結構模型時，優先參考 `references/structure-models.md`。

### Global rules
- 不要先優化原解；先驗證是否應該改問法、改流程、改責任分工、改資料邊界、改 UI、改驗證點。
- 若使用者的前提是錯的，直接指出錯在哪裡，並補一個可行替代方向。
- 若缺少問題描述、目前解法、限制條件中的任一項，先從上下文補推；若少掉會實質改變結論，再追問最少必要問題。
- 任何任務都先查核關鍵概念；若提到技術、產品、法規、近期服務、成本或規格，先上網確認再下結論。
- 每條方案都要回答四件事：核心概念、實際作法、為何更簡單或更穩、代價與風險。
- 禁止只給抽象創意；必須能指出至少一個可驗證的下一步，例如 pilot、A/B、人工試跑、流程改版或資料切分實驗。

### Step 0: Confirm inputs and evaluation target
- 先確認或補推以下資訊：
  - 問題描述
  - 目前解法
  - 限制條件
  - 真正要優化的目標，例如成本、穩定性、速度、準確率、可維護性、導入風險
- 若使用者只說「有沒有更好方法」，先把現況整理成 2-4 句白話摘要，再開始分析。
- 對任何被點名的技術、工具或方法做最小必要的網路查核，避免拿過時印象做判斷。

### Step 1: 問題本質重構
- 用一句話寫出：
  - 真正難的不是 X，而是 Y。
- 補一句說明：目前解法為何在解表面症狀，而不是根因。
- 如果使用者其實在解錯問題，直接指出並改寫成更正確的問題陳述。

### Step 2: 抽象化與結構分類
- 從 `references/structure-models.md` 選出 1-2 個最貼近的結構模型。
- 說明為何屬於這一類。
- 補上此類問題常見解法輪廓，讓使用者知道不是只剩單一路線。

### Step 3: 類比轉移與他域對照
- 至少找 2 個不同領域的同構場景。
- 每個場景都要回答：
  - 該場景怎麼解
  - 為何可以類比
  - 可以搬來用的機制是什麼
- 類比要落在機制層，不要只做表面比喻。

### Step 4: 隱含假設與限制鬆綁
- 列出目前解法依賴的前提條件。
- 區分：
  - 可放鬆的限制
  - 不能放鬆的硬限制
- 對每個可放鬆限制，補上鬆綁後才成立的新解法可能性。

### Step 5: 問題拆解與模組化
- 把現況拆成合理模組，例如輸入、處理、判斷、比對、輸出、驗證、人工介入。
- 判斷：
  - 哪段可以重排
  - 哪段可以改技術
  - 哪段可以簡化
  - 哪段其實可以整段移除
- 不要假設每個模組都必須存在。

### Step 6: 新技術引入與技術跳躍
- 主動列出使用者可能不知道，但已成熟或值得評估的技術、流程手段或產品模式。
- 每項都要標註：
  - 可解哪一段
  - 是否能讓某段流程消失
  - 成熟度是「可馬上用」還是「需評估」
- 若更好的答案其實不是新技術，而是規則化、批次化、人工分流或介面改造，也要直說。

### Step 7: 替代解法生成
- 至少提出 3 條方案，且來自不同思維類型。
- 優先從這些類型中挑 3 種以上：
  - UI / UX
  - 流程重排
  - 技術替換
  - 半自動 / 人工輔助
  - 規則取代模型
- 每條方案都要有：
  - 核心概念
  - 實際作法
  - 為何更簡單或更穩
  - 代價與風險
- 若某條方案只是原解的微調，不算替代解法。

### Step 8: 最低摩擦解
- 一定要補一條「幾乎不動系統，只改介面或流程」即可改善的方案。
- 這條方案的重點不是完美，而是低導入成本、低協調成本、可快速驗證。

### Step 9: Finalization and QA
- 對照 `references/quality_checklist.md` 自檢。
- 確認輸出至少包含：
  - 問題本質重構
  - 抽象結構分類
  - 2 個他域類比
  - 可放鬆限制
  - 模組拆解
  - 成熟技術
  - 3 條替代解法
  - 最低摩擦解
- 若其中某段證據不足，要明講「這是推論，不是已驗證事實」。

## Testing plan

### Triggering tests
- Should trigger:
  - "我不想再優化這個方案了，請幫我找替代解法。"
  - "目前做法是 OCR + LLM + 人工複核，有沒有更穩定的不同思路？"
  - "不要給我原解優化，請直接挑戰前提。"
  - "只能小改流程，怎麼用最低摩擦方式改善？"
  - "可不可以用規則取代模型？"
- Should NOT trigger:
  - "幫我把這段 React 程式碼修好。"
  - "請直接幫我寫規格文件。"
  - "幫我設計一個 landing page。"
  - "這個 SQL 太慢，幫我優化。"
  - "幫我想三個活動名稱。"
- Near-miss / confusing cases:
  - "替代方案" 其實是在問備援機制，不是要重構主方案。
  - "最小改動" 其實只是要 hotfix，不是要替代解法。
  - 使用者只給目標，完全沒給目前解法；此時要先補推現況或追問最少資訊。

### Functional tests
- Test case: 從複雜 AI pipeline 找非 AI 替代路線
  - Given: 使用者提供問題、目前解法與硬限制
  - When: 啟動本 skill
  - Then:
    - 能寫出一句本質重構
    - 至少提供 2 個他域類比
    - 至少提供 3 條不同思維類型替代解法
    - 補 1 條最低摩擦解

- Test case: 錯誤前提糾正
  - Given: 使用者把問題誤判成模型不夠強
  - When: 啟動本 skill
  - Then:
    - 能指出真正問題可能是輸入品質、流程耦合或驗證缺失
    - 不會只建議換更大的模型

- Test case: 非本 skill 範圍
  - Given: 使用者只要直接寫 spec 或直接修 bug
  - When: 啟動本 skill
  - Then:
    - 能明確說明這不是本 skill 主責
    - 交棒給更合適的 skill 或工作流

### Performance comparison
- Baseline (no skill): 常見結果是只在原方案上做微調，缺少跨域類比、限制鬆綁與多路徑替代方案。
- With skill: 結果應明顯增加問題重構品質、方案多樣性、風險評估完整度與可試行性。

### ROI guardrail
- Quality gain must justify extra:
  - Time: 只有當替代方案品質明顯提高、能避免錯誤投入時，才值得多做研究與拆解。
  - Tokens: 不為了顯得完整而塞滿抽象理論；只保留會影響決策的分析。
  - Maintenance burden: 細部模型清單與結構分類表放在 `references/`，避免把 `SKILL.md` 變成難維護長文。

### Regression gates
- Minimum pass-rate delta: `+0.10`
- Maximum allowed time increase: `45s`
- Maximum allowed token increase: `8000`
- Maximum under-trigger failures: `1 / eval batch`
- Maximum over-trigger failures: `1 / eval batch`

### Feedback loop
- Common failure signals:
  - 只是在優化原解，沒有真正替代方案
  - 三條方案其實只是同一路線的變體
  - 沒有指出錯誤前提
  - 缺少最低摩擦解
  - 類比只有比喻，沒有可搬用機制
  - 成熟技術列表像 buzzword 清單，無法連回問題模組
- Likely fix:
  - 收緊 `description` 的 trigger wording
  - 強化 Step 7 的不同思維類型要求
  - 補 `references/structure-models.md` 的結構模型與典型解法
  - 用 `assets/evals/evals.json` 補更接近真實情境的案例

## Eval workflow

- Save approved prompts to `assets/evals/evals.json`
- Define release thresholds in `assets/evals/regression_gates.json`
- Prepare paired runs with `python scripts/prepare_eval_workspace.py <path/to/skill>`
- If the environment supports subagents or parallel workers, launch with-skill and baseline runs in the same batch
- After runs complete, aggregate results and generate a review viewer
- Validate release thresholds with `python scripts/check_regression_gates.py <benchmark.json> --config assets/evals/regression_gates.json`

## Distribution notes

- Packaging: `python scripts/package_skill.py <path/to/skill-folder> <output-dir>`
- Repo-level README belongs outside this skill folder.

## Troubleshooting

- Symptom: 回答看起來很有想法，但最後仍只是原方案優化。
  - Cause: Step 1 沒有成功重構問題本質，或 Step 7 沒有檢查方案是否真的換思路。
  - Fix: 重寫「真正難的不是什麼，而是什麼」，並強制三條方案分屬不同類型。

- Symptom: 回答內容很多，但使用者無法決策。
  - Cause: 缺少代價、風險、導入成本與最低摩擦解。
  - Fix: 每條方案補齊 trade-off，並把最低摩擦解獨立成段落。

- Symptom: 過度依賴新技術推薦。
  - Cause: 把「新技術」誤當成唯一的替代解。
  - Fix: 重新檢查是否能用規則、流程重排、介面改造或人工輔助讓某段流程直接消失。

## Resources

- `references/output-template.md`
- `references/structure-models.md`
- `references/quality_checklist.md`
- `assets/evals/evals.json`
- `assets/evals/regression_gates.json`
