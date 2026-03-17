---
name: long-document-evidence-reader
description: 當需要閱讀超長 PDF、規格文件或大型程式碼庫時使用。先切片與搜尋，再彙整可追溯證據回答問題。
version: 2026.3.9
metadata:
  short-description: 長文件切片搜尋、證據彙整與可追溯閱讀工作流程
  openclaw:
    emoji: "🔍"
---

# RLM 長上下文閱讀技能

這個技能把論文提出的 **Recursive Language Model (RLM)** 具體化成一個可落地的「長文本閱讀器」：

- 把超長內容（PDF、repo、多文件資料集）**不直接塞進 LLM**，而是放進一個 **Python REPL 環境**的 `context` 變數。
- 讓根模型（root LM）透過寫程式來 **探勘 / 分解 / 篩選** `context`，並在需要語意判斷時呼叫 `llm_query()` 對「小片段」做 **遞迴子呼叫**。
- 用變數當 buffer（例如 `notes`, `evidence`, `answer_parts`），最後以 `FINAL(...)` 或 `FINAL_VAR(var)` 產生最終輸出。

## 何時要用

- 你要回答的問題依賴大量內容，或必須密集引用多段證據（例如：一整本 PDF、規格書、超大 codebase）。
- 你需要可追溯的過程（用程式碼搜尋、統計、抽樣、驗證），而不是「憑印象摘要」。
- 你懷疑會遇到 context rot：內容越長，模型越容易忘、越容易幻覺。

## 快速工作流

1. **載入內容到 `context`**
   - PDF：每頁（或每 N 字）做一個 chunk。
   - Repo：每個檔案做 chunk，前面加上檔名與路徑當 header。

2. **先做結構探勘（程式化）**
   - `len(context)`、chunk 大小分佈、抽樣印出前幾個 chunk。
   - 用 regex / 關鍵字 / 檔名過濾，先把候選範圍縮小。

3. **在需要語意的地方才用 `llm_query()`**
   - 批次化：每次塞 50k–200k 字（視模型能力），避免「每行一次」的爆炸式 subcall。
   - 用子呼叫做：分類、抽取、局部總結、核對互相矛盾的片段。

4. **把中間結果存到變數，並可驗證**
   - 例如：`evidence = [(chunk_id, quote, why_it_matters), ...]`
   - 用程式做一致性檢查：日期/數值/出處是否對得上。

5. **輸出**
   - 直接：`FINAL("...")`
   - 或長輸出：組成 `final_answer` 字串後 `FINAL_VAR(final_answer)`。

## 你可以直接用的實作

這個 skill 已經把 RLM 的 REPL 迴圈、`FINAL/FINAL_VAR` 解析、以及 PDF/repo 載入與（可選）BM25 檢索都做成可重用腳本：

- `scripts/rlm_runner.py`：RLM 主迴圈（root LM ↔ REPL ↔ sub-LM）
- `scripts/load_pdf.py`：把 PDF 轉成 chunk list
- `scripts/load_codebase.py`：把 repo 轉成 chunk list
- `scripts/bm25_index.py`：輕量 BM25（可選，用於候選段落召回）
- `scripts/demo_cli.py`：命令列示範（PDF / repo）

## 使用建議（避免踩雷）

- **先用程式把搜尋空間縮小**：regex/關鍵字/檔名先把 10M token 變 50k token。
- **子呼叫要「少而大」**：一次餵大一點、問精準一點；不要把 subcall 當 for-loop。
- **保留證據鏈**：把關鍵句子（或檔案+行號）存下來，再讓 root 做整合。
- **成本會長尾**：RLM 可能因為驗證/回圈拉長而變貴；要有 `max_steps` 與 batching 策略。
