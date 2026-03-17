# RLM 概念速查（給實作者）

這個 skill 的核心抽象完全對應論文的描述：

- **把 prompt 當成環境的一部分**：長文本不進模型 context window，而是進 REPL 的 `context` 變數。
- **互動式觀測**：root LM 先拿到 `len(context)`、chunk 分佈等概覽，再用程式碼逐步「看」需要的片段。
- **遞迴子呼叫**：遇到語意分類/抽取等，root LM 用 `llm_query()` 對小片段做子呼叫（也可讓子呼叫再採用同樣流程，形成更深層遞迴）。
- **用變數做長輸出**：把長結果存在 `final_answer` 等變數，最後 `FINAL_VAR(final_answer)`。

工程上的幾個實務點：

- **chunking 策略很重要**：PDF 通常按頁；repo 通常按檔案；超長單檔可再按字元數切。
- **先用程式化過濾再語意判斷**：regex/grep 先縮小範圍，子 LLM 只吃需要語意的候選 chunk。
- **成本長尾**：RLM trajectory 可能因重複驗證/回圈變長，務必要設 `max_steps` 與 batching。
