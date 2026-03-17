---
name: problem-decomposer
description: 當使用者要拆解大型、混亂、跨部門、反覆卡關或高不確定性的難題，或明確要求做問題拆解、issue tree、根因與對策分層時使用。先分清楚現象、目標落差、真正問題與根因假設，再判斷問題是範疇型、分析型、動態系統型、研究型或交付型，最後用 issue tree/MECE、WBS、系統思考、驗收標準、依賴排程、資源分派與流動指標，產出可執行的問題拆解報告、工作包、關鍵路徑、並行策略與 PDCA 回饋節奏。
version: 2026.3.15
metadata:
  author: Allan Yiin
  language: zh-TW
  category: problem-solving
  short-description: 將大而亂的難題轉成可驗收、可排程、可追蹤的拆解與執行報告
---

# Problem Decomposer

## Purpose

這個 skill 的工作不是把問題「切碎而已」，而是把大而亂的難題轉成可管理、可驗收、可排序、可並行的工作系統。

它會先判斷問題性質，再選擇合適的拆解視角，最後輸出可直接執行的報告，而不是只給抽象框架名詞或漂亮清單。

## Scope

### In scope
- 使用者面對的是大型、模糊、跨角色、高風險或高不確定性的問題，需要一份能直接推進工作的拆解報告。
- 需要先分清楚表象、真正問題、根因假設與對策，而不是把所有東西混成一張待辦。
- 需要把問題改寫成成功狀態、範圍邊界、工作包、驗收標準、依賴、排程、資源與指標。
- 需要判斷該用 MECE、WBS、系統思考、OKR、CPM/PERT、Kanban 或其組合。
- 需要把研究型、創新型、專案型或流程型難題拆成可做 Go/No-Go、可控風險、可持續改善的路線。

### Out of scope
- 單純要修一個 bug、寫一段程式、做一頁簡報或畫單張圖，且不需要整體拆解。
- 已經有明確 spec 或任務分工，只是要直接實作或補單一細節。
- 單純要替代解法，不是要做完整問題拆解與執行設計。
- 只想要理論介紹、書摘或概念懶人包，而不需要可執行輸出。
- 只是在問「issue tree 是什麼」或要單純框架教學，沒有要落地拆解。

## Primary use cases

1) **把混亂問題整理成可執行報告**
- Trigger examples: "這件事很大很亂，幫我拆成可以執行的步驟", "幫我把這個難題拆成工作包、依賴跟驗收方式"
- Expected result: 產出包含成功定義、框架選擇、工作包、驗收標準、依賴、風險與下一步的完整拆解報告。

2) **把跨團隊專案拆成可排程與可追蹤的計畫**
- Trigger examples: "這個跨部門專案一直推不動，幫我拆解成可排程的計畫", "請把這個專案整理成 WBS、關鍵路徑與 RACI"
- Expected result: 交付交付物導向拆解、責任分派、關鍵路徑、並行策略、WIP/節奏與回顧機制。

3) **處理反覆發生或帶副作用的系統性問題**
- Trigger examples: "這個問題解了又來，幫我找槓桿點並拆成可執行方案", "不要只列待辦，我想知道系統怎麼造成這個問題"
- Expected result: 先辨識系統結構、回饋迴路與延遲，再把槓桿點轉成工作項與監控指標。

4) **把研究或創新題轉成可驗證路線**
- Trigger examples: "這個研究題很不確定，幫我拆成 PoC、Baseline、Go/No-Go 決策", "請把創新案拆成先降風險再擴大的執行計畫"
- Expected result: 產出包含假設、Baseline、PoC、評估與決策節點的可驗證路線圖。

5) **把表象與根因分開，建立 issue tree 或對策樹**
- Trigger examples: "幫我把這個營運問題拆成 issue tree，分清楚到底卡在哪", "不要再把表象當問題，請幫我拆真正的問題與對策"
- Expected result: 先定義根問題句、拆出互斥且盡量完整的分支、標出待驗證假設，再區分短期止血與長期解法。

## Workflow overview

1. 先抽取現象、目標落差、限制、成功條件與時程壓力。
2. 先上網查核會影響拆解方式的關鍵概念、框架或外部約束。
3. 判斷問題類型，選擇主要拆解視角與輔助工具。
4. 先定義真正問題、成功狀態、In/Out、假設與風險，再開始正式拆解。
5. 視情況先做 issue tree、原因樹或對策樹，再把已驗證的分支轉成工作包。
6. 把工作拆成可驗收的工作包，補 DoD、AC、估時、依賴與資源。
7. 標出關鍵路徑、可並行區段、WIP 控制與回饋節奏。
8. 依 `references/output-template.md` 輸出可執行報告，最後做品質檢查。

## Communication notes

- User vocabulary: 難題拆解、可執行報告、工作包、依賴、並行、關鍵路徑、驗收標準、槓桿點、回饋迴路、PoC、Go/No-Go、問題拆解、issue tree、根因、對策樹。
- Avoid jargon: 若使用者未必熟框架名稱，先用白話解釋，例如把 MECE 說成「分類不重疊、不遺漏」，把 WBS 說成「交付導向拆解」。
- Least-surprise rule: 使用者要的是一份能推進工作的拆解方案，不是只列工具名或抄理論定義。
- Correction rule: 若使用者把問題當成待辦堆疊，其實是系統性或邊界定義問題，要直接指出。
- Problem framing rule: 先區分「看到的現象」「想達成的狀態」「懷疑的根因」「準備做的對策」，不要把這四者混成同一層。
- Output rule: 預設輸出結構化報告，至少包含框架選擇理由、工作包、驗收、依賴、風險、指標與最先做的 3 件事。

## Routing boundaries

- Neighboring skills / workflows:
  - `alternative-solution-designer`: 當核心是找不同解法，不是把既定難題拆成執行系統時切換。
  - `spec-organizer`: 當問題已收斂，接下來要整理成產品或系統規格時切換。
  - `long-document-evidence-reader`: 當主要瓶頸是先消化超長文件或大型程式碼庫時先切過去。
  - `mermaid-diagram`: 當需求只剩視覺化，不需要完整拆解報告時切換。
- Negative triggers:
  - "幫我直接修 bug"
  - "請做產品 spec"
  - "幫我找替代解法"
  - "畫一張 Mermaid 流程圖"
- Handoff rule: 若已經完成問題重構與拆解，接下來只剩規格化、介面設計或實作，就明確交棒，不要繼續重複拆解。

## Language coverage

- Primary language(s): 繁體中文。
- Mixed-language trigger phrases: problem decomposition、issue tree、WBS、MECE、critical path、PERT、Kanban、RACI、DoD、acceptance criteria、Go/No-Go。
- Locale-specific wording risks:
  - 「拆解」有時只是要條列待辦，不一定需要完整方法論；若只是單層任務清單，避免 over-trigger。
  - 「框架」有時只是想聽理論，不是要落地；若沒有執行需求，應縮小輸出深度。

## Success criteria

### Quantitative
- Trigger accuracy: 至少 90% 的明確難題拆解查詢能觸發。
- Output completeness: 100% 包含問題定義、框架選擇、工作包、驗收、依賴、風險、指標與下一步。
- Framework selection errors: 0 個明顯把 MECE/WBS/系統思考混為一談的案例。
- Problem framing errors: 0 個明顯把症狀、根因、對策或工作分解寫在同一層的案例。
- Tool calls: 一般案例可控制在 1-6 次必要查核；遇到時效性框架、產品、規則或產業限制時先查證再回答。

### Qualitative
- 使用者能看懂為什麼選這個拆解視角，而不是另一個。
- 報告能直接變成待辦、排程或跨團隊對齊材料。
- 子任務不是只有名稱，而是能驗收、能指派、能排優先序。
- 若問題本質被看錯，skill 能主動糾正，不沿用錯誤前提。

## Instructions

先讀 `references/framework-selection.md`、`references/problem-framing-and-issue-trees.md` 與 `references/output-template.md`；最後用 `references/quality_checklist.md` 自檢。

### Global rules
- 任何任務先查核會影響拆解結論的關鍵概念、方法、時效性規則或外部限制；若內容可能已變動，先上網確認。
- 先判斷問題性質，再選工具；不要反過來先套框架再硬湊問題。
- 明確區分 `分類`、`交付分解`、`動態系統診斷`、`目標對齊`、`排程控制` 這幾種工作。
- 每個工作包都要至少補一種完成判準：DoD、AC、決策門檻或可觀察輸出。
- 如果使用者前提錯了，直接指出錯在哪裡，並改寫成更正確的問題陳述。
- 若資訊不足，先從上下文合理補推；只有當錯誤假設會直接改變拆解結構時才追問。

### Step 0: Confirm inputs and decomposition target
- 先整理最低必要資訊：
  - 目前看到的現象或症狀
  - 期望狀態與實際差距
  - 問題描述
  - 想達成的結果
  - 已知限制
  - 時程或資源壓力
  - 已卡住的位置
- 若使用者只說「很亂」「很大」，先用 2-4 句把目前狀態重述成可操作問題。
- 若使用者把症狀直接當成問題，先改寫成「哪個結果不如預期、差多少、懷疑原因在哪」。
- 若任務其實一次性、低複雜度、低風險，直接指出不需要重型拆解，改用簡版輸出。

### Step 1: Research gate
- 先抽取 2-5 個會影響拆解方式的關鍵概念或外部約束。
- 上網查核優先順序：
  - 框架與定義：官方或權威來源
  - 專案/流程方法：官方指南、原始文件
  - 時效性限制：最新官方文件或正式文件
- 若使用者已提供參考資料，先用其內容，再以外部來源補關鍵定義或更新風險。
- 若查核結果會改變拆解方式，要在輸出中明說「因為 X，所以不用 Y，改用 Z」。

### Step 2: Classify the problem type
- 依 `references/framework-selection.md` 把問題先歸到一類或多類：
  - 可遞迴/可合併規則明確
  - 交付/範疇型
  - 分析/決策型
  - 反覆發生的動態系統型
  - 研究/創新/高不確定型
  - 目標對齊型
- 用 1-3 句說明判斷理由。
- 若問題本質是混合型，指出主框架與輔助框架，不要假裝只有一種方法。

### Step 3: Rewrite the problem as a success state
- 把原始問題改寫成：
  - 現象 / 症狀
  - 期望狀態與實際差距
  - 初步根因假設與待驗證點
  - 成功狀態
  - In scope / Out of scope
  - 假設與限制
  - 不做清單
- 若適合，補一組 Objective/KR 或里程碑。
- 成功定義要可觀察、可驗證，不接受「變更好」「變有效率」這種空泛說法。
- 若目前只知道現象，不要假裝已知根因；把根因明確標成假設。

### Step 4: Choose and apply the decomposition lens
- 若重點是分類完整性，用 MECE 或 issue tree。
- 若重點是交付與範疇，用 WBS 拆到可估時、可指派、可驗收。
- 若重點是反覆發生與副作用，用系統圖找存量、流量、回饋迴路與延遲。
- 若重點是不確定性，用 Baseline、PoC、三點估算、決策門檻。
- 若需要對齊結果，用 Objective/KR 或里程碑。
- 若使用 issue tree：
  - 先寫根問題句，讓每一層分支都回答同一個問題。
  - 同一層只能用一種分類基準，例如客群、流程階段、通路、地區、時間或原因類別。
  - 明確區分這是 `原因樹`、`對策樹` 還是 `工作分解`，不要混寫。
- 若還無法判定根因，先用 issue tree 搭配差異分析、層別法或 5 Why 收斂，再決定是否進一步做 WBS 或排程。
- 明確寫出：為什麼這個視角最適合，另外哪些框架只是輔助，而不是主要骨架。

### Step 5: Build work packages with acceptance
- 將拆解結果整理成工作包，每個工作包至少包含：
  - 名稱
  - 目的
  - 輸出
  - 驗收方式
  - 估時或不確定性
  - 依賴
- 若主框架是 issue tree 或原因診斷，先把每個主要分支整理成：
  - 分支問題
  - 目前假設
  - 需要驗證的證據
  - 驗證後可能採取的對策
- 若是系統型問題，除了工作包，還要補：
  - 哪個結構在產生問題
  - 目前槓桿點在哪裡
  - 為何不是只靠加人或加待辦
- 若是研究型問題，必須補：
  - Baseline
  - PoC
  - 評估方式
  - Go/No-Go 標準

### Step 6: Dependency, scheduling, and flow design
- 標出：
  - 關鍵路徑
  - 可並行工作
  - 高風險先行項
  - WIP 上限或節奏建議
- 若任務需要估時，優先用三點估算或等價方法處理不確定性。
- 若任務需要多人協作，補 RACI、資源瓶頸與容量假設。
- 不要只畫時間表；必須說明依賴為何如此安排。

### Step 7: Metrics and feedback loop
- 至少補一組執行追蹤機制：
  - 進度與流動指標，例如 WIP、Cycle Time、Throughput、Work Item Age
  - 品質指標，例如返工率、驗收通過率
  - 對齊指標，例如 KR 達成度、里程碑達成率
- 設定回饋節奏，例如每週檢視阻塞、雙週調整估時、月度 PDCA。
- 若問題有系統性副作用，說明要觀察哪些延遲效應。

### Step 8: Final output contract
- 依 `references/output-template.md` 輸出。
- 預設至少包含以下段落：
  - 執行摘要
  - 問題類型與框架選擇
  - 成功狀態與邊界
  - 拆解結構
  - 工作包、驗收與依賴
  - 排程與並行策略
  - 資源、風險與緩衝
  - 指標與 PDCA
  - 最先做的 3 件事
  - 待確認事項
- 若適合用表格，優先用表格；若適合用圖，允許額外產出 Mermaid，但圖不能取代文字說明。

### Step 9: Finalization and QA
- 對照 `references/quality_checklist.md` 檢查。
- 確認沒有犯下下列錯誤：
  - 把 MECE 當成 WBS
  - 把症狀直接當根因
  - 在同一層混用不同分類基準
  - 把原因樹、對策樹、工作分解寫成同一棵樹
  - 只有任務名稱，沒有驗收
  - 有時間表，卻沒依賴
  - 有看板，卻沒 WIP 或流動指標
  - 問題明明是系統性，卻只列待辦清單
  - 問題明明是研究型，卻沒有 Baseline 或決策門檻

## Testing plan

### Triggering tests
- Should trigger:
  - "幫我把這個很大很亂的專案拆成可執行報告"
  - "請把這個難題整理成 WBS、依賴、關鍵路徑與驗收標準"
  - "這個問題反覆發生，幫我用系統思考找槓桿點並拆成任務"
  - "幫我把研究題拆成 Baseline、PoC、Go/No-Go"
  - "我要一份可直接拿去排程和追蹤的難題拆解"
  - "幫我把這個營運問題拆成 issue tree，分清楚是流量、轉換還是客單價造成"
- Should NOT trigger:
  - "幫我直接修這個 bug"
  - "請做產品 spec"
  - "幫我找替代解法"
  - "畫一張 Mermaid 流程圖"
  - "幫我潤稿這篇文章"
  - "issue tree 是什麼意思？請用白話介紹"
- Near-miss / confusing cases:
  - "幫我列待辦"：如果只是簡單清單，不應啟動完整 skill。
  - "幫我規劃 roadmap"：若核心是產品策略，不一定需要本 skill 完整接管。
  - "幫我拆這個功能"：若只是規格化，應交給 `spec-organizer`。
  - "幫我分析為什麼最近營收掉了"：若只是要先做分析，不一定直接進到完整工作包與排程。

### Functional tests
- Test case: 從模糊跨部門專案產出完整拆解報告
  - Given: 使用者提供一段模糊專案描述、期限與卡點
  - When: 啟動本 skill
  - Then:
    - 先判斷問題類型
    - 補成功狀態與 In/Out
    - 產出工作包、驗收、依賴、關鍵路徑與風險
    - 補指標與 PDCA

- Test case: 系統性問題不被誤拆成待辦
  - Given: 問題反覆發生且存在延遲與副作用
  - When: 啟動本 skill
  - Then:
    - 會指出這是系統型問題
    - 會補回饋迴路與槓桿點
    - 不會只給線性任務列表

- Test case: 研究題含高不確定性
  - Given: 使用者要驗證新方法可行性
  - When: 啟動本 skill
  - Then:
    - 會要求或補出 Baseline、PoC、評估方式與 Go/No-Go 標準
    - 估時會處理不確定性

- Test case: 非本 skill 邊界
  - Given: 使用者只要 alternative approach 或完整 spec
  - When: 啟動本 skill
  - Then:
    - 會說明這不是本 skill 主責
    - 交給更貼近的 skill

- Test case: 表象與根因先分開再轉工作包
  - Given: 使用者描述的是業績下滑、客訴上升等表象，且要求做 issue tree
  - When: 啟動本 skill
  - Then:
    - 會先定義目標落差與根問題句
    - issue tree 同層使用一致的分類基準
    - 不會直接把未驗證假設寫成執行任務

### Performance comparison
- Baseline (no skill): 常見結果是只得到任務清單或大框架名詞，缺少類型判斷、驗收、依賴與回饋設計。
- With skill: 應得到可直接排程、可驗收、可追蹤、可回顧的完整執行報告。

### ROI guardrail
- Quality gain must justify extra:
  - Time: 只有在能明顯提升可執行性、降低返工或避免錯誤排程時，才值得使用完整流程。
  - Tokens: 主要花在問題類型判斷、工作包與追蹤機制，不接受空泛理論堆疊。
  - Maintenance burden: 框架對照表與輸出骨架放在 `references/`，避免把 `SKILL.md` 膨脹成難維護長文。

### Regression gates
- Minimum pass-rate delta: `+0.10`
- Maximum allowed time increase: `45s`
- Maximum allowed token increase: `7000`
- Maximum under-trigger failures: `1 / eval batch`
- Maximum over-trigger failures: `1 / eval batch`

### Feedback loop
- Common failure signals:
  - 沒先判斷問題類型就直接套框架
  - 把表象、根因、對策寫在同一層
  - 輸出只有分類，沒有工作包或驗收
  - 有工作包，沒有依賴與並行策略
  - 明明是系統型問題，卻沒有回饋迴路與延遲
  - 明明是研究型問題，卻沒有 Baseline 或決策標準
  - 只講工具，不講為何這個工具適合
- Likely fix:
  - 收緊 `description`
  - 強化 Step 2 與 Step 4 的框架選擇說明
  - 補 `references/framework-selection.md` 的判斷案例
  - 擴充 `assets/evals/evals.json` 的 near-miss 測試

## Eval workflow

- Save approved prompts to `assets/evals/evals.json`
- Define release thresholds in `assets/evals/regression_gates.json`
- Prepare paired runs with `python scripts/prepare_eval_workspace.py <path/to/skill>`
- If the environment supports subagents or parallel workers, launch with-skill and baseline runs in the same batch
- After runs complete, aggregate results and generate a review viewer
- Validate release thresholds with `python scripts/check_regression_gates.py <benchmark.json> --config assets/evals/regression_gates.json`

## Distribution notes

- Packaging: `python scripts/package_skill.py <path/to/skill-folder>`
- Repo-level README belongs outside this skill folder.

## Troubleshooting

- Symptom: 回答看起來完整，但無法直接排程或指派
  - Cause: 工作包沒有驗收標準、依賴或責任歸屬
  - Fix: 回到 Step 5 與 Step 6，補齊工作包欄位與依賴設計

- Symptom: 問題解釋很多，但仍抓不到真正卡點
  - Cause: Step 2 問題類型判斷錯誤，或把系統型問題當成一般待辦
  - Fix: 重新分類問題型態，明確補主框架與輔助框架

- Symptom: 報告有理論，沒有行動順序
  - Cause: Step 8 沒有落到「最先做的 3 件事」與排程策略
  - Fix: 重新用 `references/output-template.md` 收束成可執行報告

## Resources

- `references/framework-selection.md`
- `references/problem-framing-and-issue-trees.md`
- `references/output-template.md`
- `references/quality_checklist.md`
- `assets/evals/evals.json`
- `assets/evals/regression_gates.json`
