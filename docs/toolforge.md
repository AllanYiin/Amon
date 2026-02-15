# Toolforge

本文件說明如何初始化、安裝、撤銷與驗證 native tool。

## 初始化

建立新的 toolforge 範例：

```bash
amon toolforge init my_tool
```

會產生以下結構：

```
my_tool/
  tool.yaml
  tool.py
  README.md
  tests/
    test_tool.py
```

`tool.yaml` 支援以下欄位（向後相容）：

- 必填：`name`、`version`、`description`、`risk`、`input_schema`、`default_permission`
- 選填：`output_schema`、`examples`、`permissions`
  - `examples`：陣列，每筆為 object（可放示例 input/output）
  - `permissions`：`allow/ask/deny` 字串陣列，可對應 ToolPolicy patterns

## 安裝

將工具安裝到全域或專案：

```bash
amon toolforge install ./my_tool
amon toolforge install ./my_tool --project <project_id>
```

## 驗證

驗證已安裝工具：

```bash
amon toolforge verify
amon toolforge verify --project <project_id>
amon toolforge verify --json
```

驗證會包含：

1. 靜態檢查（manifest schema、欄位型別與一致性）
2. 測試檢查（若 `tools/<name>/tests` 存在，會執行 `python -m unittest discover -s tests -p "test_*.py"`）
3. 機器可讀輸出（`--json`）供 UI/CI 使用

## 上架/下架（soft delete）

```bash
amon toolforge revoke <name>
amon toolforge enable <name>
```

- `revoke` 會將工具狀態標記為 `disabled`（不刪除檔案）
- `enable` 會恢復為 `active`
- 狀態會同步到 `cache/toolforge_index.json` 與 `cache/tool_registry.json`

## 注意事項

- `risk=high` 的工具不可預設為 allow，會被自動降為 ask。
- `tool.yaml` / `tool.py` 需一致，否則安裝會失敗。

## 範例

可參考 `examples/native_tools/text_upper` 內的完整範例。
