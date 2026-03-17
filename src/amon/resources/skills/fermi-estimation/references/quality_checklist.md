# Fermi Estimation Quality Checklist

出貨前至少檢查一次，不要只看算式順不順。

## Structure
- [ ] 資料夾名稱與 frontmatter `name` 完全一致
- [ ] `SKILL.md` 為有效 UTF-8
- [ ] frontmatter 有 `name`、`description`、`version`
- [ ] `description` 同時描述 outcome 與 trigger 情境
- [ ] skill root 內沒有 `README.md`

## Triggering
- [ ] 明顯的「粗估」「費米估計」「量級估算」「大概有多少」查詢會觸發
- [ ] 「查官方數字」「精確查證」「數學唯一解」不會誤觸發
- [ ] `Fermi estimate`、`back-of-the-envelope`、`order of magnitude` 這類英文或混用說法能命中
- [ ] 使用者就算點名費米估計，但題目其實不適用時，仍會明確拒答

## Estimation quality
- [ ] 先做適用性判斷，而不是直接開始算
- [ ] 先定義目標值、單位、地理與時間範圍
- [ ] 至少拆成 3 個以上有邏輯關聯的因子
- [ ] 每個關鍵因子都有最可能值與理由
- [ ] 每個關鍵因子都有樂觀估計與悲觀估計
- [ ] 有明講樂觀/悲觀如何對應成結果的上下界，而不是偷設固定方向
- [ ] 公式與單位在運算過程中保持一致

## Validation quality
- [ ] 至少有一次合理性驗證或替代路徑檢查
- [ ] 會指出最敏感的假設，而不是把結果講成確定值
- [ ] 若某個因子估不出來，會先再拆細，而不是直接亂猜
- [ ] 若題目不適用，會清楚說明原因並停止

## Output quality
- [ ] 回覆包含問題定義、因子拆解、樂觀/最可能/悲觀假設、計算、上下界、驗證與侷限
- [ ] 明確區分已知錨點、推論假設與結論
- [ ] 不把粗估包裝成官方事實或精確結論

## Maintenance
- [ ] `assets/evals/evals.json` 涵蓋一般粗估、資源需求、合理性檢查與拒答案例
- [ ] `assets/evals/regression_gates.json` 已設定合理門檻
- [ ] 所有容易膨脹的輸出格式規範都已放進 `references/`
