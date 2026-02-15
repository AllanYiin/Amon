# Amon Docker 沙盒（檔案進出 + 即時執行）設計草案

## 背景與目標

本設計要為 Amon 提供「安全、可審計、可逐步落地」的 Docker 沙盒執行能力，支援：

- 將輸入檔案從 Amon project workspace 複製/掛載到隔離 container。
- 在 container 內即時執行命令（短任務、可串流 stdout/stderr）。
- 取回指定 output files，轉換成 Amon 可使用的 artifact。

> 本 PR 僅提供設計與最小型別骨架，不包含實際 Docker 或 HTTP 呼叫。

---

## 架構總覽

### 共用 runner（Single shared service）

採「共用 runner」架構：

- runner 是單一常駐服務（可由 Amon 內嵌啟動，或獨立程序部署）。
- 所有 project 共用同一 runner endpoint。
- 每次執行（/run）仍建立一個全新隔離 container，執行後即刪除。

這樣可同時取得：

- **維運簡化**：只有一個 runner 生命週期需監控。
- **隔離性**：每次 execution 不共享 process/filesystem state。
- **可擴充性**：後續可將 runner 水平擴展成多 instance + queue。

---

## 責任邊界

### Runner 責任（強制策略落點）

runner 應是唯一可以直接操作 Docker 的邊界，Amon 不直接 `docker run`。

1. 固定啟動參數（由 runner 強制，不允許 caller 任意覆寫）
   - `--network none`
   - `--read-only`
   - `--cap-drop ALL`
   - `--security-opt no-new-privileges`
   - `--pids-limit <n>`
   - `--memory <limit>`
   - `--cpus <limit>`
   - `--ulimit nofile=<soft>:<hard>`
   - `--tmpfs /tmp:rw,noexec,nosuid,size=<limit>`

2. 執行限制
   - hard timeout（runner 端強制 kill container）。
   - stdout/stderr 單次回應大小上限。
   - output files 數量與總大小上限。

3. 檔案 I/O 規則
   - 僅允許 caller 提供「相對於 workspace 的路徑」。
   - runner 必須做 path traversal 防護（拒絕 `..`、絕對路徑、符號連結逃逸）。
   - 只允許白名單輸出目錄（例如 `artifacts/` 或 caller 顯式列出的 output paths）。

4. 回應正規化
   - 統一回傳 exit_code、timed_out、stdout/stderr（截斷資訊）與 output manifest。

### Amon 責任

1. 設定與政策
   - 解析 config（global/project/cli precedence）後組出 runner request。
   - 只傳遞 runner 允許的 schema，不透傳危險 docker 參數。

2. Artifact 整合
   - 將 runner `output_files` 轉成 Amon artifact metadata（path、sha256、size、mime）。
   - 寫入既有 run/session/event 流程，供 UI 與後續工具鏈使用。

3. Tool 暴露
   - 對 LLM 先以 MCP tool 形式提供（下節說明取捨）。

---

## LLM 能力暴露：MCP tool 優先

### 建議：優先採 MCP tool adapter

理由：

1. Amon 已有 MCP server 註冊、允許/拒絕政策、catalog 快取、UI 顯示流程。
2. 可直接沿用既有「高風險工具需確認」機制。
3. 不需先改動大量 builtin tool runtime。

建議命名範例：

- `sandbox.run`：提交一次沙盒執行。
- `sandbox.health`：檢查 runner 健康狀態。

### 與 builtin tool 整合的取捨

- **MCP 優點**：最快接入現有治理層（allow/deny、catalog、審計）。
- **builtin 優點**：可減少跨進程協議成本，與 native tooling 一致。
- **決策**：第一階段用 MCP adapter 快速落地；第二階段可再評估是否增補 builtin wrapper（保持同一 request/response schema）。

---

## Runner API Schema（v1 草案）

### `GET /health`

Response 200:

```json
{
  "status": "ok",
  "service": "amon-sandbox-runner",
  "version": "0.1.0"
}
```

### `POST /run`

Request:

```json
{
  "request_id": "uuid",
  "project_id": "project-123",
  "image": "python:3.12-slim",
  "command": ["python", "main.py"],
  "working_dir": "workspace",
  "env": {
    "FOO": "bar"
  },
  "input_files": [
    "workspace/input/data.csv"
  ],
  "output_files": [
    "workspace/output/report.json"
  ],
  "limits": {
    "timeout_seconds": 30,
    "cpu_cores": 1.0,
    "memory_mb": 512,
    "pids": 128,
    "max_stdout_kb": 256,
    "max_stderr_kb": 256,
    "max_output_total_mb": 20
  }
}
```

Response 200:

```json
{
  "request_id": "uuid",
  "status": "ok",
  "exit_code": 0,
  "timed_out": false,
  "started_at": "2026-01-01T00:00:00Z",
  "finished_at": "2026-01-01T00:00:02Z",
  "stdout": "...",
  "stderr": "",
  "truncated": {
    "stdout": false,
    "stderr": false
  },
  "outputs": [
    {
      "path": "workspace/output/report.json",
      "size": 1024,
      "sha256": "...",
      "mime": "application/json"
    }
  ]
}
```

Error example:

```json
{
  "request_id": "uuid",
  "status": "error",
  "error": {
    "code": "PATH_NOT_ALLOWED",
    "message": "output path escapes workspace"
  }
}
```

---

## 安全模型

1. **Container runtime baseline**
   - network disabled (`--network none`)。
   - rootfs read-only (`--read-only`)。
   - drop all Linux capabilities (`--cap-drop ALL`)。
   - prevent privilege escalation (`no-new-privileges`)。

2. **資源限制**
   - CPU / memory / pids / ulimit 固定上限，且由 runner config 控制。
   - timeout 到期後先 SIGTERM，短暫 grace period 後 SIGKILL。

3. **檔案路徑保護**
   - request 僅接受相對路徑。
   - canonicalize 後必須仍位於 workspace 根目錄下。
   - 禁止 `..`、絕對路徑、空字串、磁碟機前綴（Windows drive）、NUL byte。

4. **輸出治理**
   - 限制輸出檔案總大小與檔案數。
   - 避免輸出敏感主機資訊（例如容器 metadata、宿主路徑）。

5. **審計與可追溯**
   - 每次 /run 記錄 request_id/project_id/image/command 摘要、執行時長、exit_code。
   - 記錄被拒絕原因（policy rejection code）。

---

## Amon client/adapter 設計

Amon 端新增 `amon.sandbox` 模組，先放 interface 與 config schema：

- `config_keys.py`：sandbox 設定鍵常數（供 UI/CLI/adapter 共用）。
- `types.py`：request/response 的 `TypedDict` 與 dataclass。
- `path_rules.py`：純函式 path validator（不含任何 docker/http side effect）。

後續 adapter 實作（後續 PR）：

- `client.py`：HTTP client（health/run），包含 retry 與 timeout。
- `artifact_adapter.py`：將 runner outputs 映射為 Amon artifact payload。

---

## 設定鍵建議（對齊 precedence）

建議放在 `config.sandbox` 節點，透過既有 ConfigLoader precedence：

- default < global < project < cli

關鍵鍵值：

- `sandbox.enabled: bool`
- `sandbox.runner_url: str`（例如 `http://127.0.0.1:8088`）
- `sandbox.default_image: str`
- `sandbox.timeout_seconds: int`
- `sandbox.memory_mb: int`
- `sandbox.cpu_cores: float`
- `sandbox.pids_limit: int`
- `sandbox.max_output_total_mb: int`
- `sandbox.max_stdout_kb: int`
- `sandbox.max_stderr_kb: int`

---

## 分階段落地計畫（每個 PR 可獨立 merge）

### PR-1（本次）

- 新增設計文件。
- 新增 `amon.sandbox` 最小型別與 config 常數。
- 新增純單元測試（config 解析 + path validator 規格）。

### PR-2

- 實作 runner service skeleton（/health、/run stub + schema validation）。
- 不接 Docker，先回傳 mock execution result（方便整合測試）。

### PR-3

- runner 接 Docker（強制安全參數 + timeout + I/O 限制）。
- 補齊 runner 端審計記錄與拒絕碼。

### PR-4

- Amon sandbox client + artifact adapter。
- 串到 MCP tool（`sandbox.run` / `sandbox.health`）與 UI tools catalog。

### PR-5

- E2E：從 Amon 呼叫 MCP sandbox tool 到 artifact 產出。
- 補文件（操作指引、風險說明、故障排除）。

---

## 非目標（本階段）

- 不在本 PR 導入任何實際 docker SDK / subprocess docker 呼叫。
- 不修改既有工具執行主流程（避免高風險耦合）。
- 不新增付費/計費邏輯。

---

## 最小可用版本（MVP）實作說明

### 1) Build sandbox image

在 repo root 執行：

```bash
docker build -t amon-sandbox-python:latest tools/sandbox/python
```

### 2) 啟動 shared runner（本機）

先安裝 runner 依賴（不影響一般 amon 安裝）：

```bash
pip install -e .[sandbox-runner]
```

啟動：

```bash
amon-sandbox-runner
```

預設監聽 `127.0.0.1:8088`，可用環境變數覆蓋：

- `AMON_SANDBOX_HOST`
- `AMON_SANDBOX_PORT`
- `AMON_SANDBOX_MAX_CONCURRENCY`
- `AMON_SANDBOX_IMAGE`

### 3) 啟動 shared runner（Docker）

```bash
docker run --rm -p 8088:8088 \
  -e AMON_SANDBOX_HOST=0.0.0.0 \
  -e AMON_SANDBOX_PORT=8088 \
  -e AMON_SANDBOX_IMAGE=amon-sandbox-python:latest \
  -v /var/run/docker.sock:/var/run/docker.sock \
  amon-runner:latest
```

> 若 runner 以容器方式執行，需能存取 Docker daemon（例如掛載 docker.sock），並評估此部署模式的主機安全風險。
> 建議優先使用 host process + rootless docker，避免在容器中直接暴露 host docker socket。

### 4) docker compose 範例

```yaml
services:
  amon-sandbox-runner:
    image: amon-runner:latest
    command: ["amon-sandbox-runner"]
    ports:
      - "8088:8088"
    environment:
      AMON_SANDBOX_HOST: 0.0.0.0
      AMON_SANDBOX_PORT: 8088
      AMON_SANDBOX_IMAGE: amon-sandbox-python:latest
      AMON_SANDBOX_MAX_CONCURRENCY: 4
```

安全預設（不掛 docker.sock）：

```bash
docker compose -f tools/sandbox/docker-compose.yml up
```

高風險模式（手動 opt-in，才掛 docker.sock）：

```bash
docker compose -f tools/sandbox/docker-compose.with-docker-sock.yml up
```

### 5) API request/response（MVP）

`POST /run`

Request:

```json
{
  "language": "python",
  "code": "print('hello')",
  "timeout_s": 10,
  "input_files": [
    {
      "path": "data/input.txt",
      "content_b64": "aGVsbG8="
    }
  ]
}
```

Response:

```json
{
  "id": "job-id",
  "exit_code": 0,
  "stdout": "hello\n",
  "stderr": "",
  "duration_ms": 15,
  "timed_out": false,
  "output_files": [
    {
      "path": "result/output.txt",
      "content_b64": "aGVsbG8=",
      "size": 5
    }
  ]
}
```
