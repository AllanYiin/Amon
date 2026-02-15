# Quickstart Project 範例

這個範例提供「最小可用 sample project + sample graph」，用來快速驗證 Amon 的 graph 執行能力。

## 這個 graph 會做什麼

1. `write_file`：建立 `docs/hello.txt`。
2. `agent_task`：請 LLM 產生簡短說明，寫入 `docs/agent_brief.md`。
3. `sandbox_run`：讀取 `/input/docs/hello.txt`，把處理結果寫到 `/output/result.txt`，最後由 Amon 回寫到 `docs/artifacts/<run_id>/sandbox_transform/`。
4. `write_file`：寫入 `docs/quickstart_result.md` 作為驗收提示。

## 前置條件

- 已安裝 Amon（例如：`pip install -e .`）。
- `agent_task` 需要可用的 provider 設定（如 `OPENAI_API_KEY` 與對應 config）。
- `sandbox_run` 需要可用的 sandbox runner / Docker 環境。

## Smoke 測試

```bash
amon projects create "Quickstart"
amon graph run --project <project_id> --graph examples/quickstart_project/graph.json
```

## 驗收重點

執行完成後，請確認專案目錄中至少出現以下檔案：

- `docs/hello.txt`
- `docs/agent_brief.md`
- `docs/quickstart_result.md`
- `docs/artifacts/<run_id>/sandbox_transform/result.txt`

如果 `agent_task` 或 `sandbox_run` 失敗，請先確認 provider 與 sandbox 設定，再重新執行。
