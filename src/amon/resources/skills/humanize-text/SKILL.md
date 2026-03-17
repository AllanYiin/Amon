---
name: humanize-text
description: 當使用者要把 AI 味太重、翻譯腔、過度制式、像機器列點的文字改寫成自然有人味的繁體中文或自然英文段落時使用。適合文案潤稿、社群貼文、Email、部落格草稿、簡報講稿與中英混寫內容；會先辨識語氣、受眾、保留事實與專有名詞，再重寫成連貫段落，預設禁止條列式與有序列表。若需求是繞過 AI 偵測、捏造個人經驗、學術作弊，或只做人類可讀數字時間格式化，則不適用。
version: 2026.3.13
metadata:
  author: Allan Yiin
  language: zh-TW
  category: writing
  short-description: 將 AI 味重或翻譯腔文字改寫成自然段落，預設禁用條列與編號列表
---

# Humanize Text

## Purpose

把生硬、重複、翻譯腔或充滿機器模板感的文字，改寫成更自然、更像真人會寫的版本，同時保留原意、事實、專有名詞與必要限制。
這個 skill 預設以繁體中文段落輸出為主，也能處理英文或中英混寫草稿；核心交付不是「騙過偵測器」，而是可讀、可信、符合受眾語境的自然文字。

## Scope

### In scope
- 把 AI 味重的草稿、翻譯腔內容、制式文案改寫成自然段落。
- 將條列式草稿、提詞、會議摘要改寫成連貫敘事或說明文字。
- 處理繁體中文、英文與中英混寫內容，預設優先符合繁中讀者閱讀習慣。
- 依使用情境調整語氣，例如社群貼文、Email、Landing page 文案、簡報講稿、客服說明。
- 在不改變核心事實的前提下，降低重複句型、過度對稱句、空泛形容詞與翻譯味。

### Out of scope
- 不協助繞過 AI 偵測、學術審查或內容真實性審核。
- 不捏造第一手經驗、虛構案例、虛構數據或假裝真人親身試用。
- 不處理 `go-humanize` 那類數字、時間、位元組單位的人類可讀格式化函式需求。
- 不做逐字翻譯器；若任務核心是翻譯準確度，應交給翻譯或在地化流程。
- 不輸出條列式與有序列表，除非使用者明確覆寫此限制。

## Primary use cases (2-3)

1) **AI 味重的繁中草稿自然化**
- Trigger examples: "幫我把這段 AI 味拿掉。", "這篇中文太像機器寫的，改得自然一點。"
- Expected result: 保留原意與資訊密度，改成自然繁體中文段落，去除模板感與重複句型。

2) **英文或中英混寫草稿改成自然可讀版本**
- Trigger examples: "把這段英文文案寫得更像真人。", "這段中英混寫很卡，幫我順一下語氣。"
- Expected result: 保留專有名詞與關鍵資訊，讓語氣一致、句子順口、混寫處理一致。

3) **把提綱、列點或摘要改寫成段落**
- Trigger examples: "不要用 bullet points，改成完整段落。", "把這份列點稿改成一段有節奏的說明文。"
- Expected result: 輸出只含段落與必要小標，不含條列式或編號列表，閱讀節奏自然。

## Workflow overview

1. 先確認任務是否屬於正當的文字自然化，而不是偵測器規避或虛構經驗。
2. 讀入原文後判斷語言、受眾、用途、期望語氣、必須保留的詞與不可更動的事實。
3. 標記主要問題來源，例如翻譯腔、被動句過多、句型重複、空泛形容詞、列表感過重、段落節奏過硬。
4. 依 `references/chinese-naturalization.md` 與 `references/source-notes.md` 選擇相應的中文或混語改寫規則。
5. 先重寫為自然段落，再做第二次整理，消除列表痕跡、教學腔開頭、過度平均的段落結構，並修正中英混排與標點一致性。
6. 用 `references/output-contract.md` 自檢，確認沒有新增事實、沒有條列式或有序列表、沒有把文章改成過度華麗或過度口語。
7. 若輸出落檔或需要機械檢查，使用 `python scripts/check_no_lists.py <file>` 驗證。

## Communication notes

- User vocabulary: humanize、AI 味、機器感、翻譯腔、像 ChatGPT 寫的、改自然、潤一下、順一下語氣、不要條列。
- Avoid jargon: 把 `nominalization` 說成「名詞化太重」，把 `passive voice` 說成「被動句太多」，把 `parallel structure fatigue` 說成「句型太整齊、太像模板」。
- Least-surprise rule: 使用者要的是更自然的文字，不是被大幅改寫立場、事實、結論或篇幅。
- Output rule: 預設只輸出自然段落與必要短標題，不輸出條列式與有序列表。

## Routing boundaries

- Neighboring skills / workflows:
  - `longform-writing-process`: 需要多人評論、多輪長文策劃與完整改稿流程時，由它接手。
  - `spec-organizer`: 任務核心是整理產品/技術規格，不是把文字改自然時，由它接手。
  - `web-search-strategy`: 若需要先查證外部事實、找引用來源、補新資料，再開始改寫時，由它先接手。
- Negative triggers:
  - "幫我騙過 AI detector"
  - "幫我偽裝成真人親身寫的心得"
  - "把 2048 bytes humanize 成易讀格式"
  - "幫我逐字翻譯這段英文"
- Handoff rule: 一旦任務從「改寫語氣與可讀性」轉成「查證事實」「做規格」「翻譯準確性」或「程式函式庫格式化」，就停止擴張本 skill 的範圍並交棒。

## Language coverage

- Primary language(s): 繁體中文、英文。
- Mixed-language trigger phrases: humanize、rewrite naturally、remove AI tone、翻譯腔、bullet points、CTA、landing page、email copy、social post。
- Locale-specific wording risks:
  - 繁體中文應優先避免中國用語直套，並保持台灣常見語感。
  - 中英混寫時，產品名、品牌名與技術名詞通常應保留官方寫法，不要硬翻。
  - 同一段落內不要同時混用過度書面與過度口語的語氣。

## Success criteria

### Quantitative (targets)
- Trigger accuracy: 至少 90% 的明顯人味重寫／去 AI 味／段落化需求能觸發。
- Tool calls: 一般案例 0-2 次；只有查規範或檢查輸出時才額外增加。
- No-list compliance: 100% 的預設輸出不得含 Markdown 條列或編號列表。
- Fact drift: 0 個未經使用者授權新增的事實或第一手經驗。

### Qualitative
- 讀起來像真人寫作，而不是機器重排同義詞。
- 中文版本符合繁中閱讀習慣，不帶明顯翻譯腔。
- 段落有節奏，不是把每句都磨成同樣長度。
- 不承諾也不追求「一定能通過偵測器」。

## Instructions

先讀 `references/chinese-naturalization.md`、`references/source-notes.md` 與 `references/output-contract.md`。若要驗證落檔結果是否違反列表禁令，使用 `python scripts/check_no_lists.py <file>`。

### Step 0: Confirm legitimacy and inputs
- 先讀現有對話與原文，判斷這是不是正當的語言自然化任務。
- 若使用者要求繞過 AI 偵測、假裝真實個人經驗、規避作業或審查，停止並把任務收斂回合法的編修與可讀性改善。
- 補齊或推導以下資訊：
  - 原文語言與目標語言
  - 受眾
  - 使用場景
  - 希望保留的專有名詞、數字、引用、立場與篇幅
  - 是否允許調整結構

### Step 1: Diagnose why the text feels machine-written
- 先標記主要問題，不要一上來直接同義詞替換。
- 常見問題包括：
  - 定義式起手、教學式前言、總結式收尾太固定
  - 句型重複，尤其連續使用「不僅…還…」「無論…都…」「首先…其次…最後…」
  - 空泛或灌水詞太多，例如「高效」「全面」「深度」「顯著」
  - 被動句、名詞化、抽象名詞過多，造成中文不順
  - 翻譯腔，例如硬套英文語序、過度保留抽象連接詞
  - 條列稿直接拼接，導致段落沒有流動感
  - 每段長度、句長與資訊密度都太平均，像模板而不像人寫作

### Step 2: Choose the rewrite mode
- 依需求選一種主模式，不要混太多：
  - `light polish`: 保留原結構，只修機器感與不順句。
  - `natural rewrite`: 重寫句型與段落節奏，但不改原意。
  - `paragraph reconstruction`: 把條列、摘要、提綱重組成連續段落。
  - `localized zh-TW`: 把中文改成更符合繁體中文讀者語感的版本。
- 若使用者沒指定，預設採 `natural rewrite`；若輸入是列點或提綱，改採 `paragraph reconstruction`。
- 若使用者提供參考段落或品牌聲音樣本，優先學它的距離感、節奏與觀點密度，不要抄原句。

### Step 3: Apply Chinese and mixed-language rules
- 繁中改寫時，優先做以下事情：
  - 把抽象名詞換成具體動作與主詞。
  - 盡量縮短連續修飾語，避免一個句子塞太多從屬子句。
  - 把英文語序硬譯的句子拆開重組，先求順，再求漂亮。
  - 對專有名詞、品牌名、產品名維持官方寫法，不自行亂翻。
  - 中英混寫時維持一套一致寫法，不要同段落反覆切換術語翻法。
  - 不要預設第一句一定先下定義；必要時可直接從觀點、場景或衝突切入。
  - 不要把每段都寫成同樣長度或同樣句法；保留人類常見的輕重不均與節奏差。
- 參考 `references/chinese-naturalization.md` 中的繁中規則、反模式與段落化方式。

### Step 4: Convert all list-like structure into prose
- 只要原文有 bullet points、數字清單、提綱式短句，就主動改寫成段落。
- 允許使用過渡語，例如「先」「接著」「最後」「因此」，但不要保留任何列表標記。
- 不要因為禁止列表而把句子硬接成超長一段；應拆成 2-4 段，每段只承載一個主要意圖。
- 除非使用者明確要求保留原結構，否則一律移除 `-`、`*`、`1.`、`1)`、`一、` 這類列表痕跡。

### Step 5: Preserve meaning and remove artificial signals
- 對照原文逐項檢查：
  - 事實有沒有改變
  - 立場有沒有被改掉
  - 專有名詞、數字、時間、法規名、產品名有沒有遺失
  - 是否無端加入個人經驗或未提供的結論
- 同時移除常見機器訊號：
  - 「以下是」「總而言之」「綜上所述」「首先／其次／最後」等教學或結案模板
  - 段首重複使用同一種轉折
  - 每句長度幾乎一致
  - 每段都像「主題句→說明→小結」的平均化模板
  - 重複的空話與安全句
  - 過於平均、缺乏重點的段落節奏

### Step 6: Final output contract
- 預設直接輸出改寫後的完成稿，不額外附分析清單，除非使用者要求說明修改原因。
- 完成稿必須符合以下條件：
  - 以自然段落為主
  - 不含條列式與有序列表
  - 不承諾偵測器結果
  - 不捏造第一手經驗
  - 若是繁中輸出，語感優先於英文直譯結構
- 若需要自檢落檔內容，執行 `python scripts/check_no_lists.py <file>`。

## Testing plan

### Triggering tests
- Should trigger:
  - "幫我把這篇中文改得不要那麼像 AI。"
  - "把這段 bullet points 改成自然段落。"
  - "這篇英文文案太公式化，humanize 一下。"
  - "幫我把翻譯腔拿掉，改成繁體中文口吻。"
  - "請把這封 email 潤成比較像人寫的，不要列點。"
- Should NOT trigger:
  - "幫我騙過 AI detector。"
  - "把這個 Go 函式庫 humanize bytes 的用法說明給我。"
  - "幫我逐字翻譯成繁體中文。"
  - "幫我整理產品 spec 與驗收條件。"
  - "幫我找最新市場資料再改寫。"
- Near-miss / confusing cases:
  - 使用者說「改自然一點」，但其實要的是翻譯準確而不是重寫語氣。
  - 使用者給的是條列式資料，但要求保留原格式；此時需要先確認是否真的要覆寫 no-list 預設。
  - 使用者提到 `humanize`，但語境其實是 bytes/time/number formatting。

### Functional tests
- Test case: AI 味重的繁中段落重寫
  - Given: 一段中文草稿，含重複句型與灌水形容詞
  - When: 啟動本 skill
  - Then:
    - 保留核心意思
    - 語氣更自然
    - 沒有條列標記

- Test case: 列點稿轉段落
  - Given: 3-5 條 bullet points 的產品說明
  - When: 啟動本 skill
  - Then:
    - 轉成 2-4 段自然段落
    - 不保留任何 `-`、`*`、`1.`、`一、`
    - 不遺失關鍵資訊

- Test case: 中英混寫文案整理
  - Given: 含英文產品名與中文說明的草稿
  - When: 啟動本 skill
  - Then:
    - 保留官方英文名稱
    - 中文段落自然
    - 混寫規則前後一致

- Test case: 教學模板腔去除
  - Given: 一段以「首先、其次、最後、總而言之」串起來的中文草稿
  - When: 啟動本 skill
  - Then:
    - 移除模板式串場
    - 段落不再平均得像講義
    - 仍保留原來的論點順序與重點

- Test case: 不當用途攔截
  - Given: 使用者要求騙過 AI detector 或假裝是真人親身經驗
  - When: 啟動本 skill
  - Then:
    - 明確拒絕該用途
    - 收斂為合法的可讀性改善建議

### Performance comparison (optional)
- Baseline (no skill): 常見失敗是只換同義詞、語氣仍像模板、保留列點、或為了「人味」亂加新事實。
- With skill: 會先診斷語病來源、明確做段落化與繁中在地化檢查，並以 no-list 規則阻止列表殘留。

### ROI guardrail
- Quality gain must justify extra:
  - Time: 多花的時間應換到更自然的段落節奏與更少人工再修。
  - Tokens: 不接受為了顯得專業而先輸出冗長分析；預設只交付完成稿。
  - Maintenance burden: 可機械檢查的限制交給 `scripts/check_no_lists.py`，不要全靠提示文字維持。

### Regression gates
- Minimum pass-rate delta: `+0.08`
- Maximum allowed time increase: `20s`
- Maximum allowed token increase: `4000`
- Maximum under-trigger failures: `1 / eval batch`
- Maximum over-trigger failures: `1 / eval batch`

### Feedback loop
- Common failure signals:
  - 仍然有條列或編號列表殘留
  - 中文看起來像把英文語序直接搬過來
  - 為了自然化而新增原文沒有的故事或結論
  - 句子雖然不同，但讀感仍像同一模板重複套用
  - 第一段永遠在下定義，最後一段永遠在做總結，像教學稿而不是人寫的文章
  - 把 `humanize` 誤接成 bytes/time formatting 或偵測器規避
- Likely fix:
  - 收緊 `description`，明講 no-list 與正當用途
  - 補 `references/trigger-evals.json`
  - 擴寫 `references/chinese-naturalization.md` 與 `references/source-notes.md` 的反模式與改寫示例
  - 針對輸出結果跑 `scripts/check_no_lists.py`

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

- Symptom: 改完還是很像機器文。
  - Cause: 只有做同義詞替換，沒有先診斷句型、翻譯腔與段落問題。
  - Fix: 回到 Step 1 重新標記問題來源，再依 `references/chinese-naturalization.md` 重寫。

- Symptom: 文意有保留，但輸出還是保留 bullet points。
  - Cause: 沒有執行 Step 4 的段落化，或沒跑 no-list 檢查。
  - Fix: 重做段落重組，並用 `python scripts/check_no_lists.py <file>` 驗證。

- Symptom: 中文讀起來像翻譯稿，不像繁中原生文。
  - Cause: 保留英文語序、被動句與抽象名詞太多。
  - Fix: 依 `references/chinese-naturalization.md` 優先改成主詞加動作的句式，減少抽象名詞堆疊。

- Symptom: 使用者其實想要翻譯或查證，不是 humanize。
  - Cause: `humanize` 一詞範圍被放太寬。
  - Fix: 依 `Routing boundaries` 交棒給翻譯或研究流程。

## Resources

- `references/chinese-naturalization.md`
- `references/source-notes.md`
- `references/output-contract.md`
- `references/quality_checklist.md`
- `references/trigger-evals.json`
- `scripts/check_no_lists.py`
- `assets/evals/evals.json`
- `assets/evals/regression_gates.json`
