---
name: concept-alignment
description: 當使用者要先做概念對齊、要求先不要執行任務本體、想先把關鍵概念/背景知識/近期重大事件查清楚，或要求「先上網整理背景再開始」時使用。適合「先做 Concept Alignment」「先對齊概念」「先幫我查關鍵概念與背景資料」「先整理定義、脈絡與近期變化」這類請求。會先用第一性原理拆解任務與歧義，立即上網蒐集原始或高可信來源，釐清名詞、單位、幣別、時間範圍、利害關係人與重要事件，最後只輸出 `## Concept Alignment` 下的三段：`### [關鍵概念]定義`、`### 收集背景知識`、`### 重大影響的具體事件`；必要時穿插附來源標註的 Mermaid 圖，但不執行任務本體，也不使用 canvas。
version: 2026.3.13
metadata:
  author: Allan Yiin
  language: zh-TW
  category: research
  short-description: 先做第一性原理導向的概念對齊與上網查證，整理成固定結構的背景筆記
---

# Concept Alignment

## Purpose

這個 skill 的工作是先把「人類的認知、機器的認知、可驗證事實」對齊，再把可直接支撐後續執行的背景知識整理成可追溯筆記。
它不是任務執行器，而是任務啟動前的研究與定義層：先用第一性原理拆出真正問題、歧義、利害關係人、時間與單位，再立即上網查證，輸出固定結構的 Concept Alignment。

## Scope

### In scope
- 使用者明確要求「概念對齊」「先不要執行、先查背景」「先把關鍵概念定義清楚」。
- 需要在正式執行任務前先釐清名詞、範圍、單位、幣別、地區、時間線、近期重大事件。
- 需要把背景知識整理成研究筆記，而不是只回一段簡短摘要。
- 需要對事件、法規、研究、數據、案例、常見誤解做帶來源的說明。
- 需要在適合時插入 Mermaid 圖，幫助說明時間線、概念結構、因果鏈或多角色互動。

### Out of scope
- 直接執行原任務本體，例如直接寫程式、做設計、寫提案、下結論或產出最終交付物。
- 使用者只提供單一固定文件，且需求是摘要、切片閱讀或證據擷取，而不是背景展開。
- 使用者明確要求不要上網，因為本 skill 的核心就是先做網路查證。
- 純自由聊天、純主觀意見題，或不需要事實核查與背景脈絡的簡單問題。

## Primary use cases (2-3)

1) **任務啟動前先做概念與背景對齊**
- Trigger examples: "先幫我做 concept alignment，不要直接做企劃。", "先對齊這個題目的關鍵概念與背景知識。"
- Expected result: 產出固定結構的背景筆記，釐清關鍵概念、必要脈絡與近期具體事件，讓後續任務不建立在錯誤前提上。

2) **事件、法規或技術主題的前置研究**
- Trigger examples: "我要研究歐盟 AI Act 對 SaaS 的影響，先做概念對齊。", "先把這個事件的來龍去脈、法規和研究資料查清楚。"
- Expected result: 釐清人事時地物、時間線、法條或標準、關鍵數據與相關研究，並直接指出錯誤或模糊前提。

3) **把複雜主題整理成可行的理解框架**
- Trigger examples: "這個題目太亂了，先把背景知識整理好。", "先幫我把概念樹、時間線和關聯講清楚。"
- Expected result: 形成可供後續寫 spec、做決策、做簡報或執行任務的共通知識底稿，必要時搭配 Mermaid 圖輔助理解。

## Workflow overview

1. 先確認這次只做概念對齊，不執行任務本體，且禁止使用 canvas。
2. 用第一性原理拆解任務的真正目標、決策點、歧義、單位、幣別、地區與時間範圍。
3. 列出為了完成後續任務必須補齊的背景知識清單，再立刻上網查證。
4. 優先蒐集原始來源、官方文件、論文、資料集與高可信二手來源，記錄日期與上下文。
5. 視需要加入 Mermaid 圖，並在圖下方標示資料來源。
6. 只用固定結構輸出 Concept Alignment，最後停止，不延伸去做主任務。

## Communication notes

- User vocabulary: 概念對齊、背景知識、關鍵概念、先不要執行、先上網查、來龍去脈、重大事件、法規、研究、數據、案例、第一性原理。
- Avoid jargon: 把 `common ground` 說成「共同理解基礎」，把 `primary source` 說成「原始來源/第一手來源」，把 `shared mental model` 說成「共享心智模型或共同理解」。
- Least-surprise rule: 使用者期待的是一份嚴謹、可追溯、能支撐後續任務的背景筆記，不是空泛百科，不是直接開始做任務，也不是只丟搜尋結果。
- Correction rule: 若使用者前提與資料衝突，要直接指出錯誤與原因，不要順著錯誤前提繼續展開。

## Routing boundaries

- Neighboring skills / workflows:
  - `web-search-strategy`: 當使用者要的是搜尋查詢設計，而不是整理概念對齊內容時，交棒給它。
  - `long-document-evidence-reader`: 當已知來源集中在單一超長 PDF、法規全文或大型程式碼庫時，先交給它抽取證據，再回來做概念對齊。
  - `mermaid-diagram`: 當主要任務是設計、除錯或美化 Mermaid 圖本身，而不是概念對齊時，交棒給它。
  - `spec-organizer`、`alternative-solution-designer`、`slide-content-planner`: 概念對齊完成後，若要轉成規格、方案或簡報，再交給相鄰 skill。
- Negative triggers:
  - "直接幫我把方案寫出來"
  - "不要查網路，直接憑經驗回答"
  - "我已經有完整 PDF，幫我摘要就好"
  - "幫我畫一張 Mermaid 圖，不需要研究"
- Handoff rule: 只要任務重心從「對齊概念與背景」轉成「閱讀固定文件」「設計搜尋策略」「產出實作/提案/規格」，就停止擴張本 skill 範圍並交棒。

## Language coverage

- Primary language(s): 繁體中文，次要支援英文術語與中英混寫來源。
- Mixed-language trigger phrases: Concept Alignment、first principles、background research、key concepts、timeline、primary source、regulation、dataset、paper、Mermaid。
- Locale-specific wording risks:
  - 「近期」一定要換成具體日期描述，不可只用模糊相對時間。
  - 「法規」必須先釐清法域；不同國家法條不可混用。
  - 「金額」必須標明幣別；「成長率/市占/成本」需標示單位與統計期間。
  - `alignment` 可能指 AI alignment、stakeholder alignment 或 concept alignment，必須先辨識脈絡。

## Success criteria

### Quantitative (targets)
- Trigger accuracy: 至少 90% 的明顯概念對齊/前置背景研究需求能命中。
- Tool calls: 一般案例 4-15 次；只有在多輪查證或跨法域/跨年份比對時才更高。
- Freshness-sensitive facts: 100% 對近期事件、法規、價格、版本、公司現況等內容做當下查證。
- Structure compliance: 100% 以 `## Concept Alignment` 和三個固定 `###` 標題輸出。

### Qualitative
- 不執行任務本體，只交付概念對齊內容。
- 關鍵主張能追溯到來源，且事實、推論、偏見/刻板印象有清楚區分。
- 圖表只在真的提高理解時才使用，且圖下有來源註記。
- 單位、幣別、時間範圍、法域與人物角色不含混。

## Instructions

### Step 0: Confirm inputs
- Read the existing conversation/files first; ask follow-up questions only when a wrong assumption would materially change the outcome.
- 不要使用 canvas。
- 先確認這次交付是「概念對齊」，不是直接執行主任務。
- 至少辨識以下資訊；若缺漏但可合理推導，可先推導並在回覆中標示假設：
  - 使用者後續想完成的主任務是什麼
  - 研究對象、地區/法域、時間範圍、受眾
  - 任何數字涉及的單位與幣別
  - 是否有使用者已提供的固定來源需要優先納入
- 若使用者要求不要上網，要直接說明這與本 skill 的核心流程衝突。

### Step 1: Decompose the task from first principles
- 先問自己：使用者真正想降低的是哪一種風險？常見是定義錯、脈絡缺失、前提錯、忽略近期變化、忽略法律/單位/幣別、或混淆因果。
- 拆出後續任務最依賴的關鍵概念、專有名詞、角色、事件、數字、地點、日期、法規與研究問題。
- 若主題含歧義，先列出可能解讀並快速判斷哪一個最符合上下文；只有在不同解讀會大幅改變研究方向時才反問。
- 先建立研究清單，再開始搜尋。研究清單至少檢查：
  - 定義與範圍
  - 事件始末與時間線
  - 相關人物、組織、地區、標準或法域
  - 公式、法規、研究、數據、資料集、案例
  - 常見誤解、偏見或大眾刻板印象
  - 近期可能改變判斷的具體事件

### Step 2: Search the web immediately with source hierarchy
- 立刻上網，不可只憑記憶整理。
- 優先順序：
  - 官方/原始來源：政府、監管機構、公司公告、標準組織、原始資料集、論文原文
  - 高可信研究來源：學術論文、學會、研究機構、大學
  - 高品質二手整理：權威媒體、專業機構報告
  - 一般新聞或評論：只用於補近期事件或輿論背景，不可當唯一證據
- 對時間敏感資訊，記錄：
  - 發布日期
  - 事件發生日期
  - 適用地區或法域
- 如果使用者前提是錯的，要直接更正並附來源，不要把錯誤前提包裝成中立意見。

### Step 3: Collect granular background knowledge
- 在 `### [關鍵概念]定義` 內，先定義核心概念與專有名詞，必要時標註：
  - 中文與英文原名
  - 適用範圍
  - 單位與幣別
  - 相近概念的差異
- 在 `### 收集背景知識` 內，先簡短列出你認為解這題需要哪些知識面向，再逐項補上細顆粒度背景知識。
- 若主題涉及事件，至少補齊人事時地物與事件始末。
- 若有公式，使用 LaTeX；若沒有，不要硬塞公式。
- 若有法規，明確寫出法規名稱、法域、條文或章節，並附官方來源。
- 若有研究，寫出論文名稱、年份、來源與 abstract 重點摘要，摘要用自己的話重述，不要長篇照抄。
- 若有數據、資料集或統計，標示資料提供者、時間範圍、指標定義與任何重要限制。
- 若有代表性案例，說明案例與主題的關聯，不要只貼流水帳。
- 明確區分：
  - 已驗證事實
  - 推論或解讀
  - 常見偏見/刻板印象與其修正

### Step 4: Use Mermaid only when it materially improves clarity
- 先判斷圖表是否真的必要；不必要就不要硬畫。
- 圖表選型依 `references/diagram-selection.md`：
  - `timeline`: 年代、法規修訂、事件演變
  - `flowchart`: 因果鏈、判斷流程、制度運作
  - `sequenceDiagram`: 多角色之間的互動與訊息交換
  - `mindmap`: 概念樹、分類結構
- 每張圖都要：
  - 以最少節點表達清楚
  - 盡量用短標籤，必要時加引號
  - 在圖下方列 `來源註記`，標出對應資料來源
- 若 Mermaid 語法或渲染風險高，回退成純文字整理，不要為了有圖而輸出容易壞掉的圖。

### Step 5: Render the final answer in the exact contract
- 第一行必須是：
  - `## Concept Alignment`
- 接著依序輸出且只輸出這三個三級標題：
  - `### [關鍵概念]定義`
  - `### 收集背景知識`
  - `### 重大影響的具體事件`
- `### [關鍵概念]定義` 中的 `[關鍵概念]` 要替換成最能代表任務的主題名稱；若主題包含多個關鍵概念，可在該段內分別說明。
- `### 收集背景知識` 中：
  - 先列你需要的知識清單，再給詳細筆記
  - 所有重要事實都附來源 annotation
  - 不相關的知識類型不要硬湊，但要覆蓋真正會影響後續任務判斷的資訊
- `### 重大影響的具體事件` 中：
  - 只列「具體事件」，不要寫抽象趨勢口號
  - 每則事件都寫出確切日期、事件內容、影響方向
  - 近期必須是相對於當下查證的近期，不可用過時印象
- 若插入 Mermaid 圖，圖要嵌在最相關段落中，且圖下方附來源註記。
- 完成概念對齊後就停止，不要再延伸到規格、方案或實作。

### Step 6: Finalization and QA
- 交付前依 `references/output-template.md` 檢查輸出順序與格式。
- 交付前依 `references/quality_checklist.md` 自檢：
  - 是否真的上網查證
  - 是否把相對時間改成具體日期
  - 是否釐清單位/幣別/法域
  - 是否清楚區分事實與推論
  - 是否避免執行任務本體
- Run `python ..\\skill-creator-advanced\\scripts\\format_check.py .`
- Run `python ..\\skill-creator-advanced\\scripts\\quick_validate.py .`

## Testing plan

### Triggering tests
- Should trigger:
  - "先做 concept alignment，先不要開始寫提案。"
  - "這個主題先幫我做概念對齊，整理關鍵概念、背景知識和近期重大事件。"
  - "請先上網查清楚這個技術/法規/事件，再幫我做背景對齊。"
  - "先不要執行，先用第一性原理把定義、法規、研究和數據整理成筆記。"
  - "幫我先把這個題目的概念樹與時間線理清。"
- Should NOT trigger:
  - "直接幫我寫 PRD。"
  - "這份 PDF 幫我摘要就好。"
  - "只幫我畫 Mermaid 圖，不用查資料。"
  - "幫我想三個替代方案。"
  - "不要上網，直接給我答案。"
- Near-miss / confusing cases:
  - 使用者說「先研究」但其實只要搜尋查詢設計，這比較像 `web-search-strategy`。
  - 使用者提供大型 PDF 與明確問題，此時應先交給 `long-document-evidence-reader` 擷取證據。
  - 使用者說 `alignment`，可能是在講 AI alignment 或 stakeholder alignment，不一定是概念對齊。
  - 使用者其實要的是最終提案或規格，概念對齊只應作為前置步驟而非主交付。

### Functional tests
- Test case: 法規主題的前置概念對齊
  - Given: 使用者要研究某法規對產品策略的影響，但要求先不要寫策略
  - When: 啟動本 skill
  - Then:
    - 先上網查法規原文或監管機構文件
    - 釐清法域、日期、條文、定義與近期修訂
    - 最終輸出三段固定標題，不直接寫策略方案

- Test case: 技術主題含研究與數據
  - Given: 使用者要研究一個技術概念，後續要做設計或實作
  - When: 啟動本 skill
  - Then:
    - 會先定義核心術語與相近概念差異
    - 會補相關研究、數據或案例並附來源
    - 若有必要會用 Mermaid 呈現概念結構或流程

- Test case: 事件主題需要時間線
  - Given: 使用者要理解一個事件的始末與近期變化
  - When: 啟動本 skill
  - Then:
    - 會整理人事時地物與具體日期
    - `### 重大影響的具體事件` 會列出近期具體事件
    - 適合時會插入有來源註記的 timeline 圖

- Test case: 應拒絕直接執行主任務
  - Given: 使用者其實要的是直接輸出最終企劃或程式
  - When: 啟動本 skill
  - Then:
    - 只交付概念對齊
    - 不偷做後續方案或實作

### Performance comparison (optional)
- Baseline (no skill): 常見失敗是直接回答、沒先查證、沒有釐清歧義、時間線混亂、單位/法域/幣別遺漏、把抽象趨勢當成具體事件。
- With skill: 先拆問題再上網查證，能穩定輸出固定結構、來源可追溯、近期事件具體且日期明確，也較不容易把錯誤前提帶進後續任務。

### ROI guardrail
- Quality gain must justify extra:
  - Time: 多花的研究時間必須換到更低的錯誤風險與更完整的任務背景，否則不值得。
  - Tokens: 不為了看起來完整而硬塞無關知識；只保留會影響後續判斷的背景內容。
  - Maintenance burden: Mermaid 選型與輸出格式等細節放在 `references/`，避免主檔過度膨脹。

### Regression gates
- Minimum pass-rate delta: `+0.10`
- Maximum allowed time increase: `90s`
- Maximum allowed token increase: `9000`
- Maximum under-trigger failures: `1 / eval batch`
- Maximum over-trigger failures: `1 / eval batch`

### Feedback loop
- Common failure signals:
  - 沒有真的上網查，只是憑既有印象整理。
  - 忘了把相對時間改成具體日期。
  - `### [關鍵概念]定義` 沒有釐清單位、幣別或相近概念差異。
  - `### 收集背景知識` 只有摘要，沒有細顆粒度證據與來源。
  - `### 重大影響的具體事件` 寫成抽象趨勢，而不是具體事件。
  - Mermaid 圖太複雜、沒有來源、或與內容無關。
- Likely fix:
  - 收緊 description 中的 trigger phrases，強化「先不要執行」「先上網整理背景」的辨識。
  - 補 `references/output-template.md` 與 `references/diagram-selection.md` 的示例與反模式。
  - 在 evals 中加入法規、技術、事件三種不同案例，測試時間線、法域與來源標註。

## Eval workflow

- Save approved prompts to `assets/evals/evals.json`
- Define release thresholds in `assets/evals/regression_gates.json`
- Prepare paired runs with `python scripts/prepare_eval_workspace.py <path/to/skill>`
- If the environment supports subagents or parallel workers, launch with-skill and baseline runs in the same batch
- After runs complete, aggregate results and generate a review viewer
- Validate release thresholds with `python scripts/check_regression_gates.py <benchmark.json> --config assets/evals/regression_gates.json`

## Distribution notes

- Packaging: `python scripts/package_skill.py <path/to/skill-folder>`
- Repo-level README belongs *outside* this skill folder.

## Troubleshooting

- Symptom: 輸出看起來像百科摘要，不像概念對齊。
  - Cause: 沒有從後續任務需求倒推需要哪些知識，只是平鋪直敘整理資料。
  - Fix: 回到 Step 1，先列研究清單與決策風險，再補資料。

- Symptom: 寫了很多近期變化，但沒有具體日期或事件。
  - Cause: 把抽象趨勢當成「重大影響的具體事件」。
  - Fix: 僅保留可定位到日期與事件本體的內容，並寫清楚影響。

- Symptom: 插了 Mermaid 圖，但資訊更亂或語法容易壞。
  - Cause: 沒有先判斷圖表必要性，或選錯圖表類型。
  - Fix: 依 `references/diagram-selection.md` 重選圖表，必要時退回純文字。

- Symptom: 最後開始直接做方案、規格或實作。
  - Cause: 忘記本 skill 只做概念對齊。
  - Fix: 在完成三段固定結構後立即停止並交棒。

## Resources

- `references/output-template.md`
- `references/diagram-selection.md`
- `references/quality_checklist.md`
- `assets/evals/evals.json`
- `assets/evals/regression_gates.json`
