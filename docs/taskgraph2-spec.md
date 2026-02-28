# TaskGraph 2.0 規格

TaskGraph 2.0 用於描述可驗證的任務 DAG，資料模型如下：

## Top-level

```json
{
  "schema_version": "2.0",
  "objective": "...",
  "session_defaults": {},
  "nodes": [],
  "edges": [],
  "metadata": {}
}
```

- `schema_version`：固定為 `"2.0"`。
- `objective`：任務總目標（非空字串）。
- `session_defaults`：初始 session key/value。
- `nodes`：`TaskNode[]`。
- `edges`：`Edge[]`。
- `metadata`：可選 object。

## TaskNode

必要欄位：
- `id`、`title`、`kind`、`description`

完整欄位：

- `role: str`（可空）
- `reads: list[str]`
- `writes: dict[str, str]`（session key -> type hint，如 `json` / `md` / `text` / `artifact_ref`）
- `llm: {model?, mode?, temperature?, max_tokens?, tool_choice?}`
- `tools: list[{name, when_to_use?, required?, args_schema_hint?}]`
- `output: {type, extract, schema?}`
  - `type`: `json|md|text|artifact`
  - `extract`: `strict|best_effort`
- `guardrails: {allow_interrupt, require_human_approval, boundaries}`
- `retry: {max_attempts, backoff_s, jitter_s}`
- `timeout: {inactivity_s, hard_s}`

## Edge

```json
{
  "from": "node-a",
  "to": "node-b",
  "when": "optional condition"
}
```

`when` 為條件分支保留欄位，目前僅做資料保存，不在 validator 執行條件判斷。

## Validator 規則

- `node.id` 必須唯一。
- `edge.from/to` 必須指向存在節點。
- 圖必須是 DAG（不可循環）。
- `node.output.type` 必須是合法值。
- `retry` 與 `timeout` 必須為正值（`jitter_s` 允許 0）。
- `reads` / `writes` 型別需符合 `list[str]` / `dict[str, str]`。

## Serialize / Deserialize

- `loads_task_graph(text)`：
  - 支援去除最外層 code fences。
  - 支援從雜訊中抽取最外層 JSON object。
  - 解析後自動執行 validator。
- `dumps_task_graph(graph)`：
  - 先驗證後序列化。
  - 輸出 stable JSON（`sort_keys=True`、固定 separators）。
