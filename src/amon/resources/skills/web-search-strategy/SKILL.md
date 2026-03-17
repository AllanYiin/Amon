---
name: web-search-strategy
description: 當使用者要上網查資料、把模糊研究意圖拆成多輪搜尋查詢、限定網站或檔案類型、找官方來源，或改善 Google/Bing 搜尋品質時使用。將問題改寫成 2-5 組高辨識度查詢，結合 site、引號、排除詞、檔案類型、搜尋引擎切換、結果去重與二次搜尋，再整理可信來源、未解空缺與下一輪查詢方向。
version: 2026.3.13
metadata:
  author: Allan Yiin
  language: zh-TW
  category: research
  short-description: 把研究問題轉成高品質搜尋策略，找到可信來源並收斂下一輪查詢
---

# Web Search Strategy

## Purpose

這個 skill 的工作不是直接把整句問題丟進搜尋框，而是先判斷使用者到底要找答案、找清單、找官方文件，還是找近期動態，再把模糊意圖改寫成高辨識度查詢與研究路徑。

它吸收 `web_tools.py` 中 `better_keywords`、`better_search`、`quick_search`、`detail_search` 的可重用策略，但會補上更嚴格的來源篩選與語法護欄：保留多組查詢、站點限制、去重、二次展開與多引擎交叉驗證，同時避免把未被官方穩定保證的語法硬寫成鐵律。

## Scope

### In scope
- 使用者要「幫我查」「幫我搜」「找官方來源」「限定某網站」「找 PDF / 年報 / 法規 / 規格」這類網路研究任務。
- 需要把模糊問題拆成 2-5 組查詢，而不是只用一條長句搜尋。
- 需要選擇適合的搜尋引擎、站點限制、檔案類型、排除詞、語言或地區線索。
- 需要先做第一輪搜尋，再依結果調整第二輪查詢。
- 需要區分官方來源、原始文件、二手整理、新聞轉述與 SEO 農場內容。

### Out of scope
- 使用者已提供明確 URL、PDF 或長文件，只需要閱讀、切片或摘要。
- 任務核心是寫 spec、寫程式、做設計、改文案，而不是搜尋策略本身。
- 單純閒聊或純意見題，不需要網路查核。
- 需要深入閱讀單一大型 PDF、論文或超長規格時，不應由本 skill 獨自處理全文閱讀。

## Primary use cases (2-3)

1) **把模糊研究意圖拆成可搜尋的查詢族**
- Trigger examples: "幫我查這個主題，但不要只搜一條關鍵字。", "把這個需求轉成比較會找到資料的搜尋方式。"
- Expected result: 產出 2-5 組查詢，每組對應不同頁面類型或證據來源，並說明各自用途。

2) **優先找官方文件、法規、PDF 或指定網站內容**
- Trigger examples: "請優先找官方文件，不要新聞轉述。", "幫我找年報 PDF 與 investor relations 頁面。"
- Expected result: 使用站點限制、檔案類型與精確短語，收斂到原始來源。

3) **多輪搜尋與來源交叉驗證**
- Trigger examples: "第一輪結果很雜，幫我縮小範圍。", "我要最新資訊，請交叉比對不同來源。"
- Expected result: 先整理第一輪搜尋缺口，再提出第二輪查詢、替代引擎與待驗證事項。

## Workflow overview

1. 先讀現有對話、檔案與已知來源，避免重搜已知資訊。
2. 判斷任務類型是 `answer`、`gathering`、`news`、`full-list`、`profile`、`dataset` 或混合型。
3. 用第一性原則推測答案最可能出現在什麼頁面類型，而不是先猜關鍵字。
4. 產出 2-5 組高辨識度查詢，每組只保留 2-3 個核心概念，必要時加站點、檔案或語言限制。
5. 根據目標選引擎與語法，執行第一輪搜尋並控制每組結果數量。
6. 去重、排除低品質來源，留下最值得打開的頁面。
7. 若證據不足，根據缺口做第二輪查詢，而不是盲目加長原查詢。
8. 最後回覆查詢策略、主要來源、未確定處與下一輪建議。

## Communication notes

- User vocabulary: 搜關鍵字、幫我查、官網資料、限定網站、找 PDF、找法規、找最新消息、交叉比對、不要垃圾結果。
- Avoid jargon: 把 `SERP` 說成「搜尋結果頁」，把 `query expansion` 說成「查詢擴寫」，把 `precision / recall` 說成「找得準 / 找得全」。
- Least-surprise rule: 不要假裝任何 operator 都穩定有效；對未被官方穩定保證的語法要標成「經驗法則」或直接改用較穩的進階搜尋 / 日期篩選。
- Output rule: 回覆至少要有查詢策略、來源類型、主要發現、未解空缺與下一輪查詢，不要只丟一串關鍵字。

## Routing boundaries

- Neighboring skills / workflows:
  - `long-document-evidence-reader`: 已經找到 PDF、法規全文或超長規格後，改由它做切片閱讀與證據整理。
  - `spec-organizer`: 研究完成後若要整理成開發 spec、驗收條件或分期計畫，交棒過去。
  - `skill-creator-advanced`: 使用者要把搜尋流程本身打包成 skill、做 eval 或發布時交棒。
- Negative triggers:
  - "幫我摘要這份 PDF"
  - "幫我直接修這段程式"
  - "幫我寫一份提案文"
  - "我只想讓你憑經驗回答，不用查網路"
- Handoff rule: 一旦來源已固定且任務重心從「找資料」變成「讀資料、寫規格、做設計或實作」，就應停止擴大搜尋，改交給更貼近主任務的 skill。

## Language coverage

- Primary language(s): 繁體中文、英文。
- Mixed-language trigger phrases: official source、site search、PDF report、annual report、exact phrase、exclude terms、query refinement、search operator。
- Locale-specific wording risks:
  - 「最新」通常代表必須真的上網查，不能沿用舊知識。
  - 「官方」有時指政府，有時指公司官網、標準組織或原始專案文件，要先辨識來源層級。
  - 「資料很多」可能是要找得更全，也可能是結果太雜；先分清楚是要擴大 coverage 還是縮小 noise。

## Success criteria

### Quantitative
- Trigger accuracy: 至少 90% 的明顯搜尋策略 / 網路研究需求能觸發。
- Query packs: 每次至少產出 2 組、至多 5 組查詢；除非使用者明確要求 full-list 掃描。
- Tool calls: 一般案例維持 3-12 次；只有在需要第二輪搜尋或交叉驗證時才增加。
- Unsupported-operator claims: 0 次把未被官方穩定保證的語法說成必定有效規則。

### Qualitative
- 不把整句問題原封不動塞進搜尋框。
- 能明確說明「這組查詢為什麼存在」以及「它預期打到哪類頁面」。
- 優先原始來源，必要時才退回新聞、部落格或二手整理。
- 能區分已驗證事實、搜尋引擎經驗法則與推論。

## Instructions

先以 `references/query-playbook.md` 作為查詢設計基準；判斷來源可信度時，使用 `references/source-triage.md`；輸出時優先套用 `references/output-template.md`。

### Global rules
- 任何任務先看現有上下文與已知檔案；若已經有精確 URL 或文件，不要重做廣泛搜尋。
- 使用者要的是研究結果，不是關鍵字拼盤；每一組查詢都要能對應到一個研究假設。
- 優先使用目前官方有文件或搜尋頁面支持的能力，例如 `site:`、精確短語、進階搜尋欄位、檔案類型與日期工具。
- 對 `before:`、`after:` 這類未穩定列在官方一般網頁搜尋說明中的語法，只能當成經驗性捷徑，不可當成保證；若時間是核心條件，優先改用搜尋工具或進階搜尋的日期限制。
- 如果使用者的前提錯了，例如把搜尋品質問題誤認為關鍵字不夠長，要直接糾正並解釋原因。

### Step 0: Confirm research target and freshness risk
- 先補齊或推導以下資訊：
  - 想找的是答案、文件、新聞、清單、公司檔案、法規、資料集，還是多者混合。
  - 是否要求最新、今日、近期、年度範圍或特定地區。
  - 來源偏好，例如官方、學術、政府、專案原始文件、投資人關係頁面。
- 若任務涉及新版本、法規、價格、公司資訊、體育、新聞等高時效內容，直接上網查，不得只憑記憶作答。

### Step 1: Classify search intent
- 依照任務把搜尋分類為：
  - `answer`: 要快速找到單一答案或少量高可信證據。
  - `gathering`: 要理解一個概念、收集多面向資料。
  - `news`: 要近期事件與時間線。
  - `full-list`: 要盡量列全，例如公司名單、工具列表、文件集合。
  - `profile` / `dataset`: 要特定主體或可下載資料。
- 這一步決定後續每組查詢的數量、每組保留結果量與是否需要第二引擎。

### Step 2: Hypothesize the page types first
- 先回答「答案最可能出現在什麼頁面」：
  - 官方說明頁
  - 法規 / 公告頁
  - PDF / 年報 / 白皮書
  - GitHub / 規格文件
  - 新聞稿或媒體報導
  - 資料集下載頁
- 這一步對應 `better_keywords` 的第一性原則：先想頁面類型，再從頁面特徵推回查詢詞。

### Step 3: Generate 2-5 query families
- 每組查詢只保留 2-3 個核心概念；若一條查詢需要四個以上主要概念，拆成兩條。
- 先放 1 個主關鍵詞，再加 1-2 個限定詞；不要把整句敘述照抄。
- 若概念本身是固定短語、產品名、法規名或公司名，優先用引號包住精確短語。
- 若已知來源網站，直接加 `site:`；若要找檔案，使用 `filetype:` 或進階搜尋的檔案類型。
- 若查詢太寬，可加排除詞或改成多組查詢，而不是瘋狂堆疊更多字。
- 若需要找完整清單，查詢數量可增加到 5 組，但每組仍要保持短而可控。

### Step 4: Choose engine and operator deliberately
- Google 與 Bing 都可用，但不要隨機切換；要說明切換原因，例如：
  - 需要官網或規格文件時，先用能更快打到原始來源的引擎。
  - 第一引擎結果過度重複、過度 SEO 化或區域偏差時，改用第二引擎做交叉驗證。
- 優先使用這些穩定技巧：
  - `site:`：限定網站或網域。
  - 引號：找精確短語、產品名、法規名、組織名。
  - 排除詞：排掉明顯錯誤語境或雜訊。
  - `filetype:`：找 PDF、XLSX 等檔案。
  - 進階搜尋 / 日期工具：控制語言、地區、最近更新。
- 若使用者要求「所有技巧」，要主動說明哪些是官方支持、哪些只是經驗性寫法。

### Step 5: Run the first search round with result caps
- `answer`: 每組通常先看前 3 個高可信結果。
- `gathering` / `profile` / `dataset`: 每組可先看前 5 個。
- `full-list`: 可擴到每組前 5-8 個，但仍要去重。
- 不要一開始就打開所有結果；先從標題、網域、摘要判斷值不值得點開。

### Step 6: Deduplicate and triage sources
- 去掉重複 URL、同站鏡像頁、內容聚合頁。
- 依 `references/source-triage.md` 的優先順序排序：
  - 官方或原始來源
  - 直接文件或原始數據
  - 權威二手來源
  - 一般新聞 / 部落格
- 若已知結果與上下文重複，優先保留新增資訊，不要重複打開同一批頁面。

### Step 7: Open only the promising pages
- 對最有機會回答問題的 3-5 頁做深入讀取。
- 若頁面其實是大型 PDF、規格或法規全文，要明確交棒給 `long-document-evidence-reader`，不要在本 skill 內硬吃整份文件。
- 若讀完仍不足以回答，記錄缺口：缺年份、缺官方來源、缺比較對象、缺定義。

### Step 8: Run the second search round from gaps
- 第二輪查詢要針對缺口，而不是把原查詢改得更長。
- 常見二次展開方式：
  - 換更精確的實體名詞
  - 改打官方站點
  - 補年度或版本
  - 改找檔案型態
  - 改用另一引擎交叉驗證
- 若查不到，不要假裝有答案；要明講找到了什麼、還缺什麼。

### Step 9: Final answer structure and QA
- 最終回覆至少包含：
  - 研究目標與假設
  - 查詢策略或查詢表
  - 主要發現
  - 仍未確定處
  - 下一輪建議查詢
  - 來源連結
- 若你引用的是搜尋技巧而不是已查證事實，標註為「策略建議」或「經驗法則」。
- 交付前用 `references/quality_checklist.md` 自檢。

## Testing plan

### Triggering tests
- Should trigger:
  - "幫我把這個題目拆成比較會找到資料的搜尋關鍵字。"
  - "我要找官方法規與公告，請不要只搜新聞。"
  - "幫我限定某網站跟 PDF，找年報。"
  - "第一輪搜尋結果太雜，幫我收斂。"
  - "請設計 Google / Bing 的搜尋策略，優先官方來源。"
- Should NOT trigger:
  - "幫我摘要這份 PDF。"
  - "幫我直接寫一份產品規格。"
  - "幫我修這段 Python 程式。"
  - "我只想讓你憑經驗回答，不要查網路。"
  - "幫我翻譯這段英文。"
- Near-miss / confusing cases:
  - 使用者說「找資料」但其實已提供 URL，此時應改用文件閱讀而非重新搜尋。
  - 使用者說「最新」但沒有指定地區，必須主動補地區或來源範圍。
  - 使用者要求時間篩選時，不應直接假設 `before:` / `after:` 是穩定支援的萬用解。

### Functional tests
- Test case: 從模糊需求產出查詢族
  - Given: 使用者只提供一段模糊研究目標
  - When: 啟動本 skill
  - Then:
    - 至少產出 2 組查詢
    - 每組查詢都說明對應頁面類型
    - 不會直接把整段原文當唯一查詢

- Test case: 官方來源優先
  - Given: 使用者要求法規、官方文件、年報或規格
  - When: 啟動本 skill
  - Then:
    - 會優先站點限制、檔案類型或原始專案來源
    - 會把新聞與二手整理降級

- Test case: 時間篩選護欄
  - Given: 使用者要求找某段時間內的最新資訊
  - When: 啟動本 skill
  - Then:
    - 會優先建議日期工具或進階搜尋
    - 若提到 `before:` / `after:`，會明講其不屬於穩定保證規則

### Performance comparison
- Baseline (no skill): 常見失敗是直接丟長句、沒有拆查詢意圖、沒有來源分級、太快下結論。
- With skill: 結果應更容易打到官方來源、重複頁更少、第二輪查詢更有針對性，且能明講不確定處。

### ROI guardrail
- Quality gain must justify extra:
  - Time: 只有在研究品質、來源可信度或搜尋效率明顯提升時，才值得做多輪搜尋。
  - Tokens: 不為了顯得專業而塞滿 operator 清單；只保留會改變搜尋結果的策略。
  - Maintenance burden: 會過時的搜尋語法細節放進 `references/`，核心流程留在 `SKILL.md`。

### Regression gates
- Minimum pass-rate delta: `+0.10`
- Maximum allowed time increase: `45s`
- Maximum allowed token increase: `7000`
- Maximum under-trigger failures: `1 / eval batch`
- Maximum over-trigger failures: `1 / eval batch`

### Feedback loop
- Common failure signals:
  - 查詢像自然語言長句，沒有拆成查詢族。
  - 沒有說明每組查詢要打哪類頁面。
  - 搜尋語法堆太多，反而讓結果變少或變怪。
  - 把經驗性 operator 說成官方穩定規則。
  - 沒有區分官方來源與二手轉述。
- Likely fix:
  - 收緊 `description` 中的觸發語句，明確強調「搜尋策略」「官方來源」「查詢拆解」。
  - 補 `references/query-playbook.md` 的查詢模式與反模式。
  - 補 `assets/evals/evals.json` 中需要日期與官方來源護欄的案例。

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

- Symptom: 給了一堆關鍵字，但結果仍然很雜。
  - Cause: 沒有先判斷頁面類型，或一條查詢塞了太多概念。
  - Fix: 先拆成多組查詢，並為每組指定站點、檔案或年份限制。

- Symptom: 搜尋結果看起來很多，但沒有可信來源。
  - Cause: 沒有做來源分級，或沒有把官方 / 原始文件放在第一層。
  - Fix: 改用 `site:`、`filetype:`、原始專案頁、政府網域或公司 IR 頁面。

- Symptom: 時間限制沒有生效。
  - Cause: 過度依賴未穩定保證的 operator，沒有用進階搜尋或日期工具。
  - Fix: 改用搜尋引擎的日期篩選、最近更新工具或站內公告時間線。

## Resources

- `references/query-playbook.md`
- `references/source-triage.md`
- `references/output-template.md`
- `references/quality_checklist.md`
- `scripts/lint_query_batches.py`
- `assets/evals/evals.json`
