# Known Limits

## 目前已知限制

### 1. 完整 test discover 可能逾時

`python -m unittest discover -s tests -p "test_*.py"` 在目前 repo 仍可能因總量與既有測試耗時而逾時。

建議至少執行：

```bash
python -m compileall src tests
python -m unittest \
  tests.test_thread_continuation_guard \
  tests.test_thread_continuation_flow \
  tests.test_ui_thread_stream_init \
  tests.test_thread_store
```

### 2. `amon ui --port 8000` 目前不會常駐前景

目前 CLI 路徑下，這個命令可能立即返回 `exit code 0`，不代表 UI server 已穩定保持在前景。發版前仍需人工確認 UI 啟動路徑。

### 3. PDF preview 仍是 metadata fallback

目前 PDF 會保留 metadata 與 fallback reason，但尚未接首頁圖像 renderer。

### 4. Workspace CLI help 輸出目前不穩定

在目前環境下，`python -m amon.cli --help` 與 `python -m amon.cli workspace --help` 可能沒有輸出。操作範例請以 README 與 `src/amon/cli.py` 為準。

### 5. 舊文件仍存在

repo 內保留不少 TaskGraph v3 cutover、sandbox、MCP、UI refactor 歷史文件。它們不是錯，但不一定是 vNext 的最佳入口。
