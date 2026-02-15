# Sandbox Integration Spec（Baseline + Guardrails）

> 狀態：**提案文件（不改動現行行為）**。
> 目標：先盤點既有 sandbox / graph / tooling / cli 能力，定義後續可安全整合的 canonical 流程與護欄。

## 0. 現況盤點（功能入口）

### 0.1 檔案位置
- `src/amon/sandbox/__init__.py`
- `src/amon/sandbox/client.py`
- `src/amon/sandbox/config_keys.py`
- `src/amon/sandbox/path_rules.py`
- `src/amon/sandbox/types.py`
- `src/amon/cli.py`
- `src/amon/graph_runtime.py`
- `src/amon/tooling.py`
- `src/amon/core.py`

### 0.2 目前入口與能力
- **CLI sandbox 入口（已存在）**：`amon sandbox exec`，讀取 runner 設定、打包 `input_files`、呼叫 runner、解碼 `output_files` 到 `--out-dir`。  
  參考：`build_parser()` 與 `_handle_sandbox(...)`。
- **Graph 執行入口（已存在）**：`AmonCore.run_graph(...)` 建立 `GraphRuntime`，於專案 `.amon/runs/<run_id>/` 產生 `state.json`、`events.jsonl`、`graph.resolved.json`。
- **Graph node 類型（已存在）**：`agent_task`、`write_file`、`condition`、`map`、`tool.call|tool_call`（目前尚無 `sandbox_run`）。
- **Tooling（已存在）**：`AmonCore.run_tool(...)` 走 legacy tool 目錄與 `tool.py` 子程序，透過 `allowed_paths` + `canonicalize_path(...)` 進行路徑限制。
- **Sandbox client（已存在）**：`SandboxRunnerClient.run_code(...)` 呼叫外部 runner；`validate_relative_path(...)` 與 `decode_output_files(...)` 提供 path traversal 防護。

---

## 1. Canonical store（project）vs runner `/input` `/output` 分工

### 1.1 原則
- **Project canonical store**：唯一真相（source of truth），所有長期保留文件與 artifact 最終都回到專案目錄（例如 `docs/`、`.amon/runs/`）。
- **Runner `/input`**：唯讀 staging 輸入區；內容由 canonical store 複製/映射而來。
- **Runner `/output`**：暫存輸出區；執行完成後由 host 驗證並回寫到 canonical store。

### 1.2 責任切分
- runner 只負責「計算」與「產生輸出檔」；
- host（Amon）負責：
  1. 輸入挑選與打包；
  2. 路徑安全驗證；
  3. 輸出白名單落地；
  4. run metadata 記錄。

---

## 2. 路徑與寫入政策（allowed_prefixes、traversal 防護）

### 2.1 `allowed_prefixes`（提案）
- sandbox 整合採顯式白名單，預設建議：
  - `docs/`（可對外可讀成果）
  - `.amon/runs/<run_id>/`（run 追蹤資料）
- 可由節點/命令細化，但不得超出專案根目錄。

### 2.2 traversal 與敏感路徑防護
- 所有相對路徑先經 `validate_relative_path(...)`：
  - 禁止空字串、`..`、`.`、絕對路徑、磁碟機前綴。
- 最終落地時再做 resolve + containment 檢查：
  - 寫入目標必須位於指定 base（例如 `out_dir` 或 project allowed prefixes）內。
- 與既有 tooling 一致，禁止觸及敏感 denylist（如 `.ssh`, `.aws` 等）。

### 2.3 寫入策略
- host 僅允許將 runner 輸出寫入 `allowed_prefixes`；超出則拒絕並記錄錯誤。
- 不允許 runner 直接覆寫 canonical store 以外路徑。

---

## 3. Staging pack / unpack 規則

### 3.1 Pack（host -> runner）
1. 先解析來源檔案清單（可由 graph node 或 CLI 提供）。
2. 每個 path 需通過 relative-path 規則與 allowed-prefix 檢查。
3. 以 `{path, content_b64}` 送入 runner `input_files`。
4. 超出大小/數量限制（`limits.max_input_*`）即 fail-fast。

### 3.2 Unpack（runner -> host）
1. 解析 runner `output_files`（必須為 list）。
2. 每個輸出 path 先做 path validation、再做 containment 檢查。
3. 僅將通過政策之檔案寫回專案目錄目標位置。
4. 超出大小/數量限制（`limits.max_output_*`）即拒絕落地。
5. 回傳 `written_files` 與統計（檔案數、bytes）。

---

## 4. Artifact 落地規則（`docs/artifacts` + `.amon/runs`）

### 4.1 目錄規劃
- 對外可讀成果：`docs/artifacts/<run_id>/...`
- 內部追蹤資料：`.amon/runs/<run_id>/sandbox/`

### 4.2 最低記錄（建議）
- `.amon/runs/<run_id>/sandbox/result.json`：
  - runner request_id / job_id
  - exit_code / timed_out / duration_ms
  - stdout/stderr 摘要（可截斷）
  - output_files manifest（path/size/hash 可選）
- `.amon/runs/<run_id>/events.jsonl` 追加 sandbox 事件：
  - `sandbox_start` / `sandbox_complete` / `sandbox_failed`

### 4.3 覆寫原則
- 同一路徑如已存在，預設採「明確覆寫」策略：
  - graph node 可透過 `overwrite` 旗標控制（預設 false）。
- 任何覆寫都應留下 run 級事件記錄。

---

## 5. Graph 新 node：`sandbox_run` schema 與行為（提案）

> 本節為 schema 提案；目前 runtime 尚未實作該 node type。

### 5.1 建議 schema
```json
{
  "id": "sandbox_step_1",
  "type": "sandbox_run",
  "language": "python",
  "code": "print('hello')",
  "code_file": "scripts/task.py",
  "input_files": [
    "docs/input/data.csv",
    ".amon/runs/{{run_id}}/context.json"
  ],
  "output_prefix": "docs/artifacts/{{run_id}}",
  "allowed_prefixes": ["docs/", ".amon/runs/{{run_id}}/"],
  "timeout_s": 30,
  "overwrite": false,
  "store_output": "sandbox_result"
}
```

### 5.2 執行語意
1. `code` 與 `code_file` 二擇一（同時提供時以 `code` 優先或直接報錯，需固定規格）。
2. 解析 template 變數後，進行 path / policy 驗證。
3. 呼叫 `SandboxRunnerClient.run_code(...)`。
4. runner `output_files` 經 unpack 落地至 `output_prefix`。
5. 寫入 run metadata（`.amon/runs/<run_id>/sandbox/result.json`）。
6. 回傳 node output：
   - `exit_code`, `timed_out`, `duration_ms`, `written_files`, `stdout`, `stderr`。
7. 若設定 `store_output`，將結果放入 graph variables。

---

## 6. CLI 新命令 `sandbox run` 行為（提案）

> 現況是 `sandbox exec`；`sandbox run` 建議作為更高階且與 graph 對齊的別名/新命令。

### 6.1 目標
- 讓 CLI 直接以「project canonical store」為中心執行 sandbox，避免使用者自行處理 unpack 落地細節。

### 6.2 建議介面
- `amon sandbox run --project <id> --language <lang> (--code-file <path>|--code <text>)`
- 可選：`--input <project_rel_path>`（可重複）、`--output-prefix <project_rel_path>`、`--timeout <sec>`。

### 6.3 行為
1. 載入 project config + runner settings。
2. 驗證 input/output path 與 allowed_prefixes。
3. 執行 runner，將 artifact 落地至 `docs/artifacts/<run_id>/`。
4. 同步寫入 `.amon/runs/<run_id>/sandbox/result.json`。
5. CLI 輸出摘要 YAML/JSON（含 written_files 與 run_id）。

---

## 7. Legacy tool sandbox backend 策略（先 opt-in）

### 7.1 為何 opt-in
- 現行 `run_tool(...)` 已有穩定流程（tool.py subprocess + allowed_paths）。
- 直接切換 backend 風險高，且會影響既有工具相容性。

### 7.2 遷移策略
- 新增可選旗標（例如 `sandbox.runner.features.use_for_tools=true`）才啟用 sandbox backend。
- 未開啟時維持現行 legacy tool backend（完全不變）。
- 啟用後先限定 low-risk 工具與明確 allowed_prefixes，逐步擴大。

### 7.3 回退策略
- 若 sandbox backend 發生 timeout/protocol error，預設直接 fail（不自動 fallback），避免雙寫不一致。
- 回退動作由設定切換控制，不在單次執行動態切換。

---

## 8. 非目標（本次）
- 不修改 `GraphRuntime` 現有 node 行為。
- 不修改 `AmonCore.run_tool(...)` 既有 backend。
- 不更動現有 CLI `sandbox exec` 行為。
- 不引入新的預設寫入路徑或自動覆寫策略。

---

## 9. 驗收建議（未來實作時）
- 單元測試：path validation、allowed_prefixes、pack/unpack 上下限、metadata 落地。
- 整合測試：
  1. graph `sandbox_run` happy path；
  2. traversal 攻擊（`../`）必拒絕；
  3. output 超限拒絕；
  4. opt-in 開/關下 tool backend 行為一致性。
