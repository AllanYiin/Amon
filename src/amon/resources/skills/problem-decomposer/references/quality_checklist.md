# Quality Checklist

在發佈這個 skill 前，至少確認下列事項。

## Triggering
- [ ] 明顯的「難題拆解」「WBS/依賴/驗收」「系統性問題拆解」「PoC/Go-No-Go 拆解」查詢會觸發。
- [ ] 單純 bug fix、spec 撰寫、替代解法、Mermaid 作圖不會誤觸發。
- [ ] 中文、英文縮寫混用時仍可判斷是否屬於本 skill。

## Problem framing
- [ ] 有先判斷問題類型，而不是直接套固定框架。
- [ ] 有先區分現象、目標落差、根因假設與對策，沒有把它們混成一層。
- [ ] 有把原問題改寫成成功狀態、In/Out、假設與限制。
- [ ] 有明確說明主框架與輔助框架，沒有把 MECE、WBS、系統思考混為一談。
- [ ] 若使用 issue tree，同一層有一致的分類基準，且區分原因樹、對策樹與工作分解。

## Execution design
- [ ] 每個工作包至少包含目的、輸出、驗收與依賴。
- [ ] 有標出關鍵路徑或可並行工作，不只是列待辦。
- [ ] 若需要多人協作，已補 RACI 或等價責任分派。
- [ ] 若問題高不確定，已補 Baseline、PoC、緩衝或決策門檻。

## System and feedback
- [ ] 系統性問題有補回饋迴路、延遲與槓桿點。
- [ ] 有至少一組追蹤指標，例如 WIP、Cycle Time、返工率或 KR 達成度。
- [ ] 有固定回饋節奏，例如週檢視、雙週調整、月度 PDCA。

## Output quality
- [ ] 最終輸出符合 `references/output-template.md` 的主體結構。
- [ ] 報告能直接轉成待辦、排程、對齊文件或決策會議材料。
- [ ] 有明確列出最先做的 3 件事與待確認事項。

## Maintenance
- [ ] `SKILL.md` 版本號已更新。
- [ ] `assets/evals/evals.json` 包含 should-trigger、should-not-trigger、near-miss。
- [ ] `assets/evals/regression_gates.json` 反映目前門檻。
