# Policy

本文件說明 Amon 的工具權限策略、工作區保護（workspace guard）與稽核記錄。

## 允許/詢問/拒絕（allow/ask/deny）

- **allow**：允許執行，不需要使用者確認。
- **ask**：需要使用者確認；若未確認則拒絕。
- **deny**：直接拒絕執行。

策略決策順序：**deny > ask > allow**。同一個工具若同時命中多個規則，以拒絕優先。

### 內建與原生工具

- **builtin**：由系統提供的內建工具，例如 `filesystem.read`。
- **native**：使用 toolforge 建立並安裝的原生工具，例如 `native:my_tool`。
- **mcp**：外部 MCP server 的工具，例如 `server:tool`。

原生工具若 `risk=high`，即使 manifest 設定為 allow，系統也會自動改為 **ask**。

## Workspace Guard

為避免工具讀寫超出工作區，Amon 會在執行前套用 **workspace guard**：

- `filesystem.*` 的 `path` / `root` 參數必須位於 workspace 內。
- `process.exec` 的 `cwd` 必須位於 workspace 內。

這能避免工具在不受控的路徑中讀寫或執行命令。

## 稽核記錄（Audit Log）

工具呼叫會寫入 JSONL 格式的稽核紀錄：

- 預設路徑：`~/.amon/logs/tool_audit.jsonl`（可透過 `AMON_HOME` 調整）。
- 每筆紀錄包含 `ts_ms`、`session_id`、`project_id`、`tool`、`decision`、`duration_ms`、`args_sha256`、`result_sha256`、`source` 等欄位。

為避免敏感資訊外洩，稽核內容**不會直接寫入參數與結果**，只會存：

- `args_sha256` / `result_sha256`：完整內容的 SHA-256 哈希。
- `args_preview` / `result_preview`：經過遮罩的結構摘要。

