# RLM 論文速查（給技能作者/維護者）

這份 reference 只放「足以操作」的重點與 prompt 片段，避免讓 SKILL.md 腫脹。

## 核心概念

- 把長 prompt 視為 **外部環境的一個物件**，而不是直接餵給 Transformer。
- 在一個持久的 REPL 環境中：
  - `context` = 長內容（str 或 List[str]）
  - `print()` 讓 root LM 看到節選輸出
  - `llm_query()` 讓 root LM 在需要語意時遞迴呼叫子 LM

論文中用 Python REPL 來示範，並指出：
- 單純把 prompt 反覆 summary/compaction 會丟失細節，不適合需要密集存取的任務。
- RLM 在資訊密集的 long-context 任務（如 OOLONG / OOLONG-Pairs）提升很明顯。

## Prompt 模板

請直接看 `scripts/rlm_prompts.py`，裡面放了 Appendix D 的 system prompt（以及 Qwen 的 batching diff）。

## 常見有效策略（來自論文的 trajectory 觀察）

- 先用 regex/關鍵字做 cheap filter，再對候選 chunk 做子呼叫語意抽取。
- chunking：常見是依換行或固定字數分塊。
- 以變數保存子呼叫輸出（buffer），最後再一次整合。
- 注意成本長尾：過度驗證/過多 subcalls 會讓成本爆炸。
