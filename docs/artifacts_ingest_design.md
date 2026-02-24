# Artifacts Ingest 設計（Phase 0）

## 目標與範圍
- 目標：定義 artifact ingest 的掛載層級、輸入格式（code fence）、輸出限制與 manifest schema，供後續 Phase 實作。
- 範圍：僅定義規格與策略，不改動既有執行流程。

## 現況盤點（GraphRuntime 寫檔落點）

### 1) `agent_task` / `write_file` 的落地流程
- `agent_task`：在 `GraphRuntime._execute_node()` 內呼叫 `core.run_agent_task(...)` 取得文字後，透過 `_resolve_output_path(...)` 解析路徑，最後 `atomic_write_text(output_path, response)` 寫檔。
- `write_file`：同樣在 `GraphRuntime._execute_node()` 內以 `_resolve_output_path(...)` 解析路徑後 `atomic_write_text(safe_path, content)` 寫檔。
- `_resolve_output_path(...)` 會做 canonicalize，並強制輸出僅能位於 `docs/` 或 `audits/`，超出即拋錯。

### 2) single / self_critique / team 三路徑是否寫入 `docs/`
- single graph：`single_task.output_path = docs/single_${run_id}.md`。
- self_critique graph：`draft_path`、`reviews_dir/review_*.md`、`final_path` 均位於 `docs/`。
- team graph：`TODO.md`、`ProjectManager.md`、`team_plan_*.md`、`tasks/*`、`audits/*`、`final.md` 皆由 graph node 指向 `docs/`（含 `docs/audits/*`）。

**結論**：以 GraphRuntime 寫入 `docs/...` 作為 ingest 主要輸入來源可行，且可覆蓋三種模式。

## Hook 點決策

### 決策
- **主掛點：GraphRuntime（優先）**
  - 原因：三種模式都經由 graph node 寫檔，且 `agent_task`/`write_file` 寫檔責任集中於同一層。
  - 建議掛點：在 `_execute_node()` 完成寫檔後，進行「內容解析 → artifact 擷取 → workspace 寫入 → manifest 落盤」。
- **補強掛點：chat/cli（次要 fallback）**
  - 僅在非 GraphRuntime 路徑（若未來新增直寫流程）時啟用。
  - 預設關閉（opt-in），避免改變既有對外行為。

## Code Fence 規格（嚴格）

### 允許格式（唯一）
只接受以下開頭格式（第一行）：

```text
```<lang> file=<relative_path>
...
```
```

- `<lang>`：`[A-Za-z0-9_+.-]+`（例如 `python`、`ts`、`bash`）。
- `file=`：必填，且必須是**單一路徑 token**（不允許空白、不允許引號包裹、不允許多個 key-value）。
- `relative_path`：僅接受相對路徑，不可為絕對路徑。

### 明確拒絕/忽略
以下視為無效 block，**不得 ingest**：
- ` ```lang`（缺少 `file=`）。
- ` ``` file=...`（缺少 lang）。
- ` ```lang path=...`、`filename=...`、`output=...` 等非 `file=` 鍵。
- ` ```lang file="a.py"`（引號包裹）。
- 同行多屬性（如 ` ```lang file=a.py mode=...`）。
- 非 fence 形式（縮排 code、~~~ fence、自然語言描述「請建立 xxx.py」）。

## 寫入根目錄與路徑限制

### 決策
- 預設只允許寫入：`<project>/workspace/**`。
- `file=` 最終寫入目標：`<project>/workspace/<relative_path>`。

### 安全規則
- 必須 canonicalize 後驗證 prefix；禁止 path traversal（`..`、符號連結逃逸等）。
- 禁止絕對路徑與磁碟代號（如 `C:\`）。
- 若目標不在 `<project>/workspace/` 下，直接拒絕該 block 並記錄錯誤事件。

## Manifest Schema（v1）

```json
{
  "version": "1",
  "run_id": "<graph_run_id>",
  "node_id": "<graph_node_id>",
  "source": {
    "kind": "graph_runtime",
    "mode": "single|self_critique|team|unknown",
    "doc_path": "docs/...md"
  },
  "artifacts": [
    {
      "index": 0,
      "lang": "python",
      "declared_file": "src/main.py",
      "workspace_path": "workspace/src/main.py",
      "bytes": 123,
      "sha256": "...",
      "status": "written|skipped|rejected",
      "reason": ""
    }
  ],
  "summary": {
    "total_blocks": 1,
    "written": 1,
    "skipped": 0,
    "rejected": 0
  },
  "ts": "2026-01-01T00:00:00Z"
}
```

### 欄位規範
- `doc_path`：來源文件（通常為 `output_path`）。
- `declared_file`：fence 中的 `file=` 原值。
- `workspace_path`：實際落盤相對專案路徑（固定前綴 `workspace/`）。
- `status`：
  - `written`：成功寫入；
  - `skipped`：格式不符或策略忽略；
  - `rejected`：安全/驗證失敗（如 traversal）。

## 錯誤策略
- 原則：**ingest 失敗不應讓主 graph run 失敗**（預設 fail-open），但需完整可追蹤。
- 記錄方式：
  - `events.jsonl` 增加 ingest 事件（成功/略過/拒絕/例外）。
  - manifest 必須保留每個 block 的 `status/reason`。
- 錯誤分級：
  - `WARNING`：格式不符、無可 ingest 區塊；
  - `ERROR`：I/O 失敗、schema 例外、安全驗證失敗。
- 去敏感：不得把 secrets 寫入 manifest/log（沿用既有規範）。

## 後續 Phase 實作建議（非本階段）
- 新增 ingest parser（嚴格 regex / state machine）。
- 將 ingest 行為做成 feature flag（預設關閉）。
- 補上單元測試：合法 fence、模糊 fence 拒絕、path traversal、manifest 內容校驗。
