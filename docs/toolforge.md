# Toolforge

本文件說明如何初始化、安裝與驗證 native tool。

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
```

若 tool.yaml 欄位不完整或 risk 設定不合理，會在輸出中標示 `VIOLATION`。

## 注意事項

- `risk=high` 的工具不可預設為 allow，會被自動降為 ask。
- `tool.yaml` / `tool.py` 需一致，否則安裝會失敗。

## 範例

可參考 `examples/native_tools/text_upper` 內的完整範例。
