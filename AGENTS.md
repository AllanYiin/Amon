# Codex 工作契約（Repo Root）

本文件適用於整個 repo，供 Codex 與人類協作時一致遵守。

## 1) 修改原則（必遵守）
### **修改原則**
  若是對既有專案做修改，理解此次改動的關鍵目的，在完成此目的的前提下：
  - 只能改動與bug或重構直接相關的區塊
  - 不得改變任何對外可觀察行為（characterization/contract tests 必須全過）
  - 除非特別要求指定，儘量不破壞原有 API / 資料結構 / 前端路由。
  - 不要把整個架構翻掉，除非使用者明說要重構或換技術。
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

# continuation guard（PR 必跑，需與 CI 一致）
python -m unittest \
  tests.test_chat_continuation_guard \
  tests.test_chat_continuation_flow \
  tests.test_ui_chat_stream_init \
  tests.test_chat_session_store

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


## 5) 續聊回歸防線（CI）
- GitHub Actions `Chat Continuation Guard` 會在 PR 自動執行，失敗即阻擋合併。
- 新增續聊相關變更時，請優先擴充 deterministic 測試（禁止依賴外部模型隨機輸出）。
