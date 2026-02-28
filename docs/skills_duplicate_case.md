# Skills 重覆內容案例（完整清單）

以下依據使用者提供資料，列出目前可觀察到的重覆 skill 案例。

## 判定規則

同一個 `name` 與 `description`，同時出現在：

1. `C:\Users\allan\.amon\skills\<skill-name>.skill`
2. `C:\Users\allan\.amon\skills\<skill-name>\SKILL.md`

即視為「同內容的雙來源重覆」。

## 重覆案例列表（9 組）

| skill name | source A | source B | description（節錄） |
|---|---|---|---|
| automation-scheduler | `...\\automation-scheduler.skill` | `...\\automation-scheduler\\SKILL.md` | 建立定期任務（每日晨報、每週回顧）。 |
| data-analysis | `...\\data-analysis.skill` | `...\\data-analysis\\SKILL.md` | 對 CSV/Parquet/JSON 資料進行分析。 |
| document-workflows | `...\\document-workflows.skill` | `...\\document-workflows\\SKILL.md` | 輸出 doc/報告（markdown/docx）。 |
| incident-triage | `...\\incident-triage.skill` | `...\\incident-triage\\SKILL.md` | log/錯誤快速定位（搭配 filesystem.grep、audit.log_query）。 |
| mcp-integration-debug | `...\\mcp-integration-debug.skill` | `...\\mcp-integration-debug\\SKILL.md` | MCP server 連不上、tools/list/call 出錯時的診斷和除錯。 |
| repo-code-review | `...\\repo-code-review.skill` | `...\\repo-code-review\\SKILL.md` | 對指定的程式碼檔案或目錄進行審查。 |
| research-brief | `...\\research-brief.skill` | `...\\research-brief\\SKILL.md` | 網頁/文件摘要、研究整理。 |
| spec-to-tasks | `...\\spec-to-tasks.skill` | `...\\spec-to-tasks\\SKILL.md` | 將一份需求規格拆成可執行任務（含驗收條件）。 |
| spreadsheet-workflows | `...\\spreadsheet-workflows.skill` | `...\\spreadsheet-workflows\\SKILL.md` | 報表 xlsx（整理、公式、檢核）。 |

## 單一案例（逐字示意）

以 `automation-scheduler` 為例，兩個來源的 metadata 皆為：

```json
{
  "name": "automation-scheduler",
  "description": "建立定期任務（每日晨報、每週回顧）。當使用者需要設定自動化的、定期執行的任務時使用。"
}
```

可據此視為同一 skill 內容被 `.skill` 與解包後 `SKILL.md` 各保存一份。
