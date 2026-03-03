# Quickstart Project 範例

這個範例提供 TaskGraph v3 的最小可用 sample graph，示範 v3 結構與遷移後的節點關係。

## 這個 graph 會做什麼

1. 包含 4 個 `TASK` 節點：`write_hello`、`agent_brief`、`sandbox_transform`、`write_result_note`。
2. 對應輸出檔案已轉為 `ARTIFACT` 節點，並以 `DATA/EMITS` 邊表示。
3. 任務先後依賴以 `CONTROL/DEPENDS_ON` 表示。

## 前置條件

- 已安裝 Amon（例如：`pip install -e .`）。
- `agent_task` 需要可用的 provider 設定（如 `OPENAI_API_KEY` 與對應 config）。
- `sandbox_run` 需要可用的 sandbox runner / Docker 環境。

## 驗證（TaskGraph v3）

```bash
python scripts/validate_all_v3_graphs.py
amon graph migrate --help
```

## 驗收重點

執行後應顯示所有 examples/fixtures graph JSON 均為 `taskgraph.v3` 且 schema 驗證成功。


## 一鍵驗證腳本

```bash
bash scripts/verify_usable.sh
```
