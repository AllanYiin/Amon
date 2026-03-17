# RLM（Recursive Language Model）設計筆記（給技能維護者）

本 skill 主要把論文中的核心抽象落地成「可執行的 REPL 迴圈」與「長文本載入工具」。

## 論文核心直覺

- 把長 prompt 當成外部環境的一部分，不直接塞進 Transformer，而是讓模型以符號方式互動（例如在 Python 內做 slicing、regex、分塊），需要語意時才對片段做子模型查詢。
- RLM 的 REPL 環境讓模型：
  1) **觀察**（print 片段、統計、抽樣）
  2) **行動**（regex/切片/排序/合併，甚至建立索引）
  3) **遞迴**（對片段呼叫 `llm_query`）
  4) **持久化狀態**（把中間答案存到變數，最後拼回總答案）

## 這個技能的工程化決策

- `ContextStore`：統一把 PDF / repo / 長文轉成 `List[Chunk]`，每個 chunk 都有 `source` 方便回溯。
- `ReplSession`：用單一 `globals` dict 模擬 persistent REPL；捕捉 stdout 並做截斷。
- `RLMRunner`：
  - 支援 `FINAL(...)` 與 `FINAL_VAR(x)`。
  - 對每回合 root LM 提供「上次 REPL 的輸出」以及「context 統計資訊」，讓模型能決策。
  - 允許設定 `max_steps`，避免無限迴圈。
- `llm_query`：預設走 provider（例如 OpenAI HTTP）；也可以替換成內網模型、或在測試用 mock。

## 常見失敗模式

- 子呼叫爆炸：一行一 subcall（成本與延遲爆表）。→ Template B 的 batching 提醒、或在 runner 層加硬限制。
- root 把計畫誤當 FINAL：→ runner 僅在字串尾端匹配 FINAL；實務可要求 root 用更嚴格格式。
- 證據遺失：只有摘要沒有引用。→ 建議在 REPL 變數中存 `evidence`（source + 片段）。

