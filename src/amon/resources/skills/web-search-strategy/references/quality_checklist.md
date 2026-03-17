# Search Research Quality Checklist

出貨前至少檢查一次，不要只看內容漂亮。

## Structure
- [ ] 資料夾名稱與 frontmatter `name` 完全一致
- [ ] `SKILL.md` 為有效 UTF-8
- [ ] frontmatter 有 `name`、`description`、`version`
- [ ] `description` 同時描述 outcome 與 trigger 情境
- [ ] skill root 內沒有 `README.md`

## Triggering
- [ ] 明顯的「幫我查 / 幫我搜 / 找官方來源 / 限定網站 / 找 PDF」查詢會觸發
- [ ] 「摘要文件 / 修程式 / 寫 spec / 翻譯」不會誤觸發
- [ ] 中英混用詞如 `official source`、`site search`、`annual report PDF` 能命中
- [ ] 「最新」或時效性任務會驅動真的上網查，而不是只用既有知識

## Search quality
- [ ] 至少先做一次意圖分類，而不是直接生成查詢
- [ ] 每次回覆至少 2 組查詢或明確說明為何單組足夠
- [ ] 每組查詢都對應特定頁面類型或研究假設
- [ ] 沒有把長句原封不動當唯一查詢
- [ ] 會優先原始來源與官方網站
- [ ] 會做去重與低品質來源排除

## Operator safety
- [ ] 把 `site:`、引號、排除詞、檔案類型等穩定技巧與經驗法則分開說
- [ ] 若提到 `before:` / `after:`，有明講這是經驗性捷徑，不是穩定保證
- [ ] 需要時間限制時，優先建議日期工具或進階搜尋

## Output quality
- [ ] 回覆包含查詢策略、主要發現、未解空缺與下一輪建議
- [ ] 若查不到，會明講證據不足，不會硬補答案
- [ ] 若找到長文件，會交棒給更適合的閱讀 skill

## Maintenance
- [ ] `assets/evals/evals.json` 含真實研究場景
- [ ] `assets/evals/regression_gates.json` 已設定合理門檻
- [ ] `scripts/lint_query_batches.py` 可正常執行
- [ ] 任何會隨搜尋引擎變動的細節都已放進 `references/` 而非硬寫在主流程
