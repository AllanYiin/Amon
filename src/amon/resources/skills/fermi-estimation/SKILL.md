---
name: fermi-estimation
description: 當使用者要在資料不足、難以直接取得精確數據時做費米估計使用。適合「幫我粗估有多少」「估算市場規模、需求量、店數、人力、容量」「用費米問題拆解這個量級」這類請求；會先判斷題目是否真的適合費米估計，再定義目標值與單位、拆成可估子問題、替每個因子給出合理假設與範圍、算出中心值與上下界，最後做數量級驗證與敏感度檢查。若題目其實需要精確查證、官方統計、正式數學解答或高風險精準結論，直接說明不適用並婉拒用本方法回答。
version: 2026.3.11
metadata:
  author: Allan Yiin
  language: zh-TW
  category: analysis
  short-description: 用費米估計拆解未知量，輸出合理假設、計算過程、結果範圍與驗證
---

# Fermi Estimation

## Purpose

這個 skill 的工作不是假裝知道精確答案，而是在資訊稀缺的情況下，用少量已知錨點、經驗法則與合理假設，做出可檢查的數量級估算。
它會把大問題拆成較小、較容易估的因子，明示每個假設的依據與不確定性，再組合出中心值與合理範圍；如果題目不適合用費米估計，會直接指出並停止。

## Scope

### In scope
- 城市店數、需求量、容量、人力、時間、資源消耗等缺乏完整資料的粗估題。
- 需要用「人口 x 行為率 x 容量」或類似分解方式做數量級判斷的問題。
- 需要檢查某個說法是否在量級上合理，例如市場規模、產能、客流量或活動需求。
- 允許結合少量可查得的錨點資料與其餘合理假設，但核心仍是估算，不是全面資料蒐集。

### Out of scope
- 使用者明確要最新官方數字、精確統計值或可直接查到的現成答案。
- 純數學證明、代數推導、微積分解題或有唯一正解的考題。
- 法律、醫療、金融、工程安全等高風險任務中，不能接受粗估誤差的精準判斷。
- 連合理拆解後仍無法給任何負責任假設的題型；此時應直接說明不適合費米估計。

## Primary use cases (2-3)

1) **估算某個場域的數量或規模**
- Trigger examples: "幫我用費米估計算台北市大概有多少家早餐店。", "不要查現成資料，粗估這個城市需要多少家咖啡店。"
- Expected result: 先界定地理範圍與單位，再拆成需求面與供給面因子，給出中心值與範圍。

2) **粗估系統或營運資源需求**
- Trigger examples: "用費米估計幫我算每天百萬請求大概要多少客服人力。", "幫我粗估這個 AI 服務需要多少 GPU。"
- Expected result: 將流量、轉換率、峰值、處理能力拆開估，輸出低中高三組結果與敏感因子。

3) **檢查敘述是否在量級上合理**
- Trigger examples: "這個展覽一天會有 50 萬人流合理嗎？", "請用費米問題驗證這個市場規模說法。"
- Expected result: 先找上界、下界與關鍵限制，判斷該說法在量級上是否站得住腳。

## Workflow overview

1. 先判斷題目是否真的適合費米估計，若不適合就明確拒答。
2. 定義估算目標、單位、地理範圍與時間範圍。
3. 把目標拆成多個可估的子問題或因子。
4. 為每個因子提供最可能值，並補樂觀估計與悲觀估計作為邊界。
5. 組合運算，算出中心值，以及由樂觀/悲觀情境形成的上下界。
6. 用替代路徑、已知常識或物理上限做 sanity check，必要時調整假設。
7. 以清楚結構回覆結果、敏感因子、限制與不確定性。

## Communication notes

- User vocabulary: 粗估、大概多少、量級、費米問題、費米估計、拆解估算、back-of-the-envelope、order of magnitude。
- Avoid jargon: 把 `sanity check` 說成「合理性驗證」，把 `order of magnitude` 說成「數量級」，把 `anchor` 說成「錨點資料」。
- Least-surprise rule: 使用者期待看到的是可追溯的假設與計算，不是直接丟一個數字；若題目不適合費米估計，必須直接說明而不是硬算。

## Routing boundaries

- Neighboring skills / workflows:
  - `web-search-strategy`: 任務核心是找最新官方數字、法規或精確事實時交棒。
  - `knowledge-framework-applier`: 使用者是要套分析框架，而不是估算未知量時交棒。
  - `spec-organizer`: 已經得到粗估結果，接下來要整理成開發或執行規格時交棒。
- Negative triggers:
  - "幫我查 2025 年台灣出生人口官方數字。"
  - "解這題微積分。"
  - "直接告訴我這家公司最新市值。"
  - "我要投資決策用的精準財務預測。"
- Handoff rule: 一旦答案可以且應該透過直接查證得到，或任務對精度要求高於粗估可接受範圍，就停止費米估計並改用查證或其他更適合的工作流。

## Language coverage

- Primary language(s): 繁體中文，次要支援英文方法名與中英混寫請求。
- Mixed-language trigger phrases: Fermi estimate、Fermi problem、rough estimate、back-of-the-envelope、order of magnitude、sanity check。
- Locale-specific wording risks:
  - 「估算」有時其實是在要精準預測，需先確認容許誤差。
  - 「大概」不代表可以隨便猜，仍需拆解與說明假設。
  - 使用者提到「費米」但題目若可直接查到官方值，仍要指出不該硬用費米估計。

## Success criteria

### Quantitative (targets)
- Trigger accuracy: 至少 90% 的明顯粗估 / 量級估算需求能命中。
- Output completeness: 100% 包含目標定義、因子拆解、假設、計算、範圍與驗證。
- Tool calls: 一般案例 0-4 次；只有在補最小必要錨點資料或驗證現實約束時才增加。
- Failures: 0 次把粗估包裝成精確事實；0 次在明顯不適用時硬做費米估計。

### Qualitative
- 若某個因子無法合理估，就會繼續細分而不是直接亂猜。
- 會清楚標示哪些是已知錨點、哪些是推論假設、哪些是不確定範圍。
- 會提供最可能值，以及樂觀/悲觀兩端情境形成的區間。
- 能用第二條估算路徑或常識邊界檢查結果是否離譜。

## Instructions

使用 `references/output-template.md` 的段落順序作為預設輸出骨架，交付前對照 `references/quality_checklist.md` 自檢。

### Global rules
- 先判斷「這題是否真的該用費米估計」，不要因為使用者提到費米就無條件套用。
- 如果能查到且應該查到精確值，直接指出用費米估計是錯的方法，並婉拒用本 skill 作答。
- 可以補少量穩定錨點資料，但不把整題改成大量研究；此 skill 的核心仍是拆解與估算。
- 每個重要假設都要附上來源類型或理由，例如日常經驗、公開常識、場景上限、保守中性值。
- 如果某個參數無法提出合理值，先再拆一層；若仍無法合理化，就停止並說明此題不適用。

### Step 0: Confirm inputs
- Read the existing conversation/files first; ask follow-up questions only when a wrong assumption would materially change the outcome.
- 至少確認以下資訊：
  - 要估算的目標值是什麼
  - 單位是什麼
  - 地理範圍與時間範圍是什麼
  - 使用者要的是粗估範圍、中心值，還是合理性檢查
- 若題目其實是最新官方數字、精確查詢或正式數學求解，直接回覆不適合費米估計並停止。

### Step 1: Define the target clearly
- 用一句話重寫問題，寫清楚估算標的、單位與時間尺度。
- 先決定輸出要回答的是「總量」「速率」「容量」「家數」「人力」還是「是否合理」。
- 若地理或時間範圍模糊，先用最少必要假設補上，並明講是假設。

### Step 2: Decompose into solvable factors
- 把大問題拆成 3-7 個可估因子，優先使用乘法鏈、加總、流量平衡或供需拆法。
- 每個子問題都必須與目標值有清楚邏輯關聯。
- 若拆完仍有模糊黑箱參數，繼續細分，直到每個因子都能被合理估。

### Step 3: Assign assumptions and ranges
- 對每個因子給：
  - 最可能值
  - 樂觀估計
  - 悲觀估計
  - 理由
- 優先使用中性估計，不故意極端保守或極端樂觀。
- 先判斷該題的樂觀情境與悲觀情境分別對結果造成什麼方向的影響，再把兩者映射成結果的下界與上界；不要預設樂觀一定較大或較小。
- 若有少量穩定錨點資料可查，先做最小必要查核並明示哪些因子來自查核。

### Step 4: Combine the numbers
- 清楚列出公式，不要只給最後答案。
- 至少算出一組中心值，並用樂觀/悲觀情境推得結果區間。
- 單位要在每一步都一致，避免人數、戶數、天數、次數混用。

### Step 5: Validate and adjust
- 用至少一種方式做合理性驗證：
  - 換一條估算路徑
  - 用物理或營運上限檢查
  - 與常識量級比對
- 若中心值與驗證結果衝突，回頭調整最敏感的假設，並說明為什麼改。

### Step 6: Final answer structure
- 最終回覆至少包含：
  - 題目是否適合費米估計
  - 問題定義與單位
  - 因子拆解
  - 假設表或條列
  - 計算過程
  - 最可能值，以及由樂觀/悲觀情境形成的上下界
  - 驗證與敏感因子
  - 侷限與注意事項
- 如果題目不適用，明確說明不適用原因，不要硬算。

### Step 7: Finalization and QA
- 對照 `references/output-template.md` 檢查輸出是否完整。
- Validate outputs against the checklist in `references/quality_checklist.md`
- Run `python ..\\skill-creator-advanced\\scripts\\format_check.py .`
- Run `python ..\\skill-creator-advanced\\scripts\\quick_validate.py .`

## Testing plan

### Triggering tests
- Should trigger:
  - "請用費米估計估算台北市大概有多少家早餐店。"
  - "幫我粗估這個 AI 產品每天百萬請求需要多少客服人力。"
  - "用 Fermi estimate 幫我判斷這個市場規模說法合不合理。"
  - "不要查現成統計，請把這個問題拆成費米問題來估。"
- Should NOT trigger:
  - "幫我查台灣 2025 年出生人口官方數字。"
  - "幫我解這題線性代數。"
  - "直接查這家公司的最新年營收。"
  - "我要能拿去送審的工程精算。"
- Near-miss / confusing cases:
  - 使用者說「估算」但其實是要官方數字，此時必須拒絕用費米估計。
  - 使用者說「費米問題」但題目是純數學唯一解，不應誤觸發。
  - 題目雖是粗估，但若缺少地理或時間範圍，需先補最小必要假設。

### Functional tests
- Test case: 城市早餐店數量估算
  - Given: 使用者要估某城市大概有多少家早餐店，且不要求精確統計
  - When: 啟動本 skill
  - Then:
    - 會先定義城市範圍與時間尺度
    - 會拆成人口、消費頻率、店家服務能力等因子
    - 會給出最可能值，以及樂觀/悲觀上下界

- Test case: 系統資源需求粗估
  - Given: 使用者要粗估高流量服務所需人力或機器資源
  - When: 啟動本 skill
  - Then:
    - 會拆出總流量、峰值、處理時長與單位產能
    - 會指出最敏感假設
    - 會用樂觀/悲觀情境與替代路徑做 sanity check

- Test case: 量級合理性檢查
  - Given: 使用者要驗證某個客流量、銷量或市場規模敘述是否合理
  - When: 啟動本 skill
  - Then:
    - 會優先找上界與限制條件
    - 會回覆「合理 / 偏高 / 偏低」及原因

- Test case: 不適用題型拒答
  - Given: 使用者要求最新官方統計或有唯一正解的數學題
  - When: 啟動本 skill
  - Then:
    - 會直接說明這不是費米估計適用題型
    - 不會硬湊估算流程

### Performance comparison (optional)
- Baseline (no skill): 常見失敗是直接憑感覺丟單一數字、沒有拆解假設、沒有範圍，也沒有驗證。
- With skill: 會強制做適用性判斷、拆解、假設說明、範圍估算與合理性檢查，降低亂猜風險。

### ROI guardrail
- Quality gain must justify extra:
  - Time: 只有在能明顯提升粗估可追溯性與可信度時，才值得多做拆解與驗證。
  - Tokens: 不把回覆寫成百科；只保留會影響結果的因子、假設與驗證。
  - Maintenance burden: 常用輸出結構與檢查規則放在 `references/`，避免主流程膨脹。

### Regression gates
- Minimum pass-rate delta: `+0.08`
- Maximum allowed time increase: `25s`
- Maximum allowed token increase: `4000`
- Maximum under-trigger failures: `1 / eval batch`
- Maximum over-trigger failures: `1 / eval batch`

### Feedback loop
- Common failure signals:
  - 直接報答案，沒有拆解與假設
  - 因子估值過度武斷，沒有理由
  - 不提供樂觀/悲觀上下界，只給單點值
  - 沒有 sanity check
  - 對明顯不適用題型沒有拒答
- Likely fix:
  - 收緊 `description` 中對粗估、量級、費米問題的 trigger wording
  - 補強 `references/output-template.md` 對樂觀/悲觀/最可能三組假設與驗證段落的要求
  - 在 `assets/evals/evals.json` 增加拒答與合理性檢查案例

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

- Symptom: 回答只有一個數字，看不出怎麼來的。
  - Cause: 沒有遵守拆解與假設揭露流程。
  - Fix: 回到 Step 2 與 Step 3，重新列出因子、假設與公式。

- Symptom: 估值很飄，無法判斷是否合理。
  - Cause: 關鍵因子拆得不夠細，或沒有提供上下界。
  - Fix: 再細分最敏感的因子，補低中高三組值與理由。

- Symptom: 明明能查到官方值，卻還在做費米估計。
  - Cause: 適用性判斷失敗，誤把查證題當成粗估題。
  - Fix: 依 Step 0 直接拒絕用本 skill 作答，改交棒給研究流程。

## Resources

- `references/output-template.md`
- `references/quality_checklist.md`
- `assets/evals/evals.json`
- `assets/evals/regression_gates.json`
