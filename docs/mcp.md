# MCP

本文件說明 MCP server 設定、快取、允許清單，以及常見問題。

## Server 設定

MCP 設定寫在全域 config：`~/.amon/config.yaml`（或 `AMON_HOME` 指定的資料夾）。

範例：

```yaml
mcp:
  servers:
    local_stub:
      transport: stdio
      command: ["python", "-m", "tests.mcp_stub_server"]
  allowed_tools:
    - "local_stub:add"
  denied_tools:
    - "local_stub:delete"
```

> 目前僅支援 `stdio` transport。

## 允許/拒絕工具

- `allowed_tools`：明確允許的 MCP 工具（格式 `<server>:<tool>`）。
- `denied_tools`：明確拒絕的 MCP 工具。

若同時在 allow 與 deny 中，**deny 優先**。

## MCP 快取

工具列表會快取在：

- `~/.amon/cache/mcp_registry.json`
- `~/.amon/cache/mcp/<server>.json`

使用 CLI 重新整理：

```bash
amon tools mcp-list --refresh
```

## 常見問題

### DENIED_BY_POLICY

表示工具不在 allow 清單中，或被 deny 清單拒絕。請更新 `mcp.allowed_tools` 後再試。

### MCP tool 呼叫失敗

常見原因：

- MCP server 未啟動
- `command` 設定錯誤
- 版本不相容

請先確認 MCP server 可正常啟動，再使用 `amon tools mcp-list` 檢查可用工具。
