# Codex 工作契約（Repo Root）

本文件適用於整個 repo，供 Codex 與人類協作時一致遵守。

## 1) 最小變更原則（必遵守）
- 只做完成需求所需的最小修改。
- 禁止無關重構、禁止順手改風格、禁止變更既有 API/資料結構（除非需求明確要求）。
- 所有 PR 必須附上實際執行命令與結果；若有失敗需附原因摘要。

## 2) 必跑檢查（每個 PR 都要過）
> 若環境受限，至少需通過 compileall，並在 PR 說明註明受限原因。

```bash
# format
# 目前未配置 black/ruff/prettier，維持 N/A

# static check / lint
python -m compileall src tests

# test
python -m unittest discover -s tests -p "test_*.py"

# dev server
amon ui --port 8000
```

## 3) 驗收條件（本次修復重點）
- 對話回覆必須「帶上文」：可延續先前使用者目標與上下文，不可每輪重置。
- 回覆結尾不得固定使用反問句（例如每次都以「要不要我幫你...？」收尾）。
- 若需求有明確輸出格式，必須完全對齊後再結案。

## 4) 安全與品質
- 嚴禁提交任何 secrets（API Key/Token/密碼）。
- 金鑰僅可放環境變數（如 `OPENAI_API_KEY`）。
- 錯誤不可吞沒：需提供可追蹤訊息，必要時寫入 logs。
