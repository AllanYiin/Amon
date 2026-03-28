# Amon

Amon 是一套以專案為中心的本地 AI 工作台。當前主線架構已收斂為：

`amon.manifest.v1 -> planner / binder / compiler -> compiled taskgraph.v3 -> TaskGraph3Runtime`

這代表：
- 手寫與持久化來源逐步收斂到 `amon.manifest.v1`
- `TaskGraph3Runtime` 仍是唯一正式執行 substrate
- `single`、`self_critique`、`team` 已轉成 template library，不再是 runtime primitive
- LLM 節點、planner、模板節點都必須以 streaming event 對 UI / CLI 輸出

詳細規格見 [SPEC_v1.2.2.md](D:/PycharmProjects/Amon/SPEC_v1.2.2.md)。

## 文件地圖

- 快速開始與 repo 入口：本文件
- vNext 規格： [SPEC_v1.2.2.md](D:/PycharmProjects/Amon/SPEC_v1.2.2.md)
- migration： [docs/migration_manifest_v1.md](D:/PycharmProjects/Amon/docs/migration_manifest_v1.md)
- runtime： [docs/runtime_vnext.md](D:/PycharmProjects/Amon/docs/runtime_vnext.md)
- tool policy： [docs/tool_policy.md](D:/PycharmProjects/Amon/docs/tool_policy.md)
- workspace UI： [docs/ui_workspace.md](D:/PycharmProjects/Amon/docs/ui_workspace.md)
- template 撰寫： [docs/template_authoring.md](D:/PycharmProjects/Amon/docs/template_authoring.md)
- 已知限制： [docs/known_limits.md](D:/PycharmProjects/Amon/docs/known_limits.md)
- 發版檢查： [RELEASE_CHECKLIST.md](D:/PycharmProjects/Amon/RELEASE_CHECKLIST.md)

## 安裝

```bash
pip install -e .
```

目前 [pyproject.toml](D:/PycharmProjects/Amon/pyproject.toml) 沒有定義 `sandbox-runner` extra，因此不要使用 `pip install -e .[sandbox-runner]`；那條指令目前只會退化成一般安裝，並額外出現 warning。

若要使用 sandbox runner，安裝本專案後直接使用已註冊的 console script：

```bash
amon-sandbox-runner
```

必要環境變數與 staged rollout flags 可參考 [.env.example](D:/PycharmProjects/Amon/.env.example)。

## Feature Flags

vNext 目前仍採 flag 控制，預設皆關閉：

```text
AMON_VNEXT_MANIFEST=0
AMON_VNEXT_BINDER=0
AMON_VNEXT_RUNTIME=0
AMON_VNEXT_UI=0
```

## 快速開始

### 1. 初始化與建立專案

```bash
amon init
amon project create "Amon vNext Demo"
```

若要在初始化後嘗試另開 command 視窗啟動 sandbox runner，正確旗標是：

```bash
amon init --start-sandbox
```

列出與查看專案：

```bash
amon project list
amon project show <project_id>
```

### 2. 啟用 vNext 路徑

```bash
set AMON_VNEXT_MANIFEST=1
set AMON_VNEXT_BINDER=1
set AMON_VNEXT_RUNTIME=1
set AMON_VNEXT_UI=1
PowerShell 可改用：

```powershell
$env:AMON_VNEXT_MANIFEST = "1"
$env:AMON_VNEXT_BINDER = "1"
$env:AMON_VNEXT_RUNTIME = "1"
$env:AMON_VNEXT_UI = "1"
```

### 3. 用 workspace CLI 建 definition / run

```bash
amon workspace projects summary --project <project_id>
amon workspace definitions list --project <project_id> --kind workflows
amon workspace runs create --project <project_id> --template single --variables "{\"prompt\":\"請整理目前 repo 的 vNext 狀態\"}"
amon workspace runs stream --project <project_id> <run_id> --follow
```

### 4. 啟動 UI

```bash
```

UI 主工作台與 streaming / preview / confirmation 的互動說明見 [docs/ui_workspace.md](D:/PycharmProjects/Amon/docs/ui_workspace.md)。

## 常用指令範例

### Project / Config

```bash
amon project list
amon project show <project_id>
amon project update <project_id> --name "New Name"
amon config show --project <project_id>
amon config get providers.openai.model --project <project_id>
```

### 單次執行與互動

```bash
amon run --project <project_id> --mode single --prompt "請整理 docs 與 examples 現況"
amon run --project <project_id> --mode self_critique --prompt "請寫一份 migration 摘要"
amon run --project <project_id> --mode team --prompt "請拆解 vNext 收尾工作"
amon chat --project <project_id>
```

### Workspace Definitions

```bash
amon workspace definitions list --project <project_id> --kind tasks
amon workspace definitions list --project <project_id> --kind agents
amon workspace definitions list --project <project_id> --kind executors
amon workspace definitions list --project <project_id> --kind workflows
amon workspace definitions get --project <project_id> --kind workflows <workflow_id>
amon workspace definitions create --project <project_id> --kind workflows --file workflow.json
amon workspace definitions update --project <project_id> --kind workflows <workflow_id> --file workflow.json
amon workspace definitions delete --project <project_id> --kind workflows <workflow_id>
```

### Workspace Runs

```bash
amon workspace runs list --project <project_id>
amon workspace runs get --project <project_id> <run_id>
amon workspace runs create --project <project_id> --workflow workflow.spec_pipeline --variables "{}"
amon workspace runs create --project <project_id> --template single --variables "{\"prompt\":\"請整理目前 repo 的 vNext 狀態\"}"
amon workspace runs resume --project <project_id> <run_id>
amon workspace runs cancel --project <project_id> <run_id>
amon workspace runs archive --project <project_id> <run_id>
amon workspace runs stream --project <project_id> <run_id> --follow
```

### Upload / Preview / Confirmation

```bash
amon workspace uploads list --project <project_id>
amon workspace uploads add --project <project_id> .\\sample.pdf --notes "需求附件"
amon workspace uploads get --project <project_id> <asset_id>
amon workspace uploads preview --project <project_id> <asset_id>
amon workspace confirmations list --project <project_id>
amon workspace confirmations approve --project <project_id> <confirmation_id>
amon workspace confirmations reject --project <project_id> <confirmation_id>
```

### Trigger 與 Daemon

```bash
amon hooks list
amon schedules list
amon jobs list
amon daemon --tick-interval 5
```

### Tool / Artifact / Sandbox

```bash
amon tools list --project <project_id>
amon tools mcp-list --refresh
amon artifacts list --project <project_id>
amon artifacts check --project <project_id>
amon sandbox run --project <project_id> --language python --code-file .\\script.py --output-prefix docs
```

## canonical manifest 與 examples

- manifest example： [examples/manifests/spec_pipeline.manifest.json](D:/PycharmProjects/Amon/examples/manifests/spec_pipeline.manifest.json)
- template examples： [examples/templates/single.template.json](D:/PycharmProjects/Amon/examples/templates/single.template.json)、 [examples/templates/self_critique.template.json](D:/PycharmProjects/Amon/examples/templates/self_critique.template.json)、 [examples/templates/team.template.json](D:/PycharmProjects/Amon/examples/templates/team.template.json)

## 目前完成狀態

- Stage 0：vNext 骨架與 feature flags
- Stage 1：manifest v1 domain model 與 storage
- Stage 2：planner / binder / compiler
- Stage 3：runtime dispatcher、tool policy、confirmation、audit
- Stage 4：template library 與 preset compatibility
- Stage 5：checkpoint / resume / preview / UI state
- Stage 6：workspace API / CLI / UI
- Stage 7：hooks / schedules / jobs 全部改走標準 run request
- Stage 8：contract tests、failure injection、run stream reconnect

## 測試

最小必要檢查：

```bash
python -m compileall src tests
python -m unittest \
  tests.test_thread_continuation_guard \
  tests.test_thread_continuation_flow \
  tests.test_ui_thread_stream_init \
  tests.test_thread_store
python -m unittest tests.smoke.test_vnext_imports
python -m unittest tests.smoke.test_vnext_ui_smoke
python -m unittest tests.smoke.test_vnext_examples_smoke
```

完整 `python -m unittest discover -s tests -p "test_*.py"` 在目前 repo 仍可能逾時，詳見 [docs/known_limits.md](D:/PycharmProjects/Amon/docs/known_limits.md)。

## 相容性原則

- 舊 `taskgraph.v3` graph 仍可作為 compiled artifact 執行
- 新 manifest source 一律先 compile 再跑
- 舊 preset 入口保留相容轉發，但內部已走 template instantiate
- unresolved refs 一律 compile-time fail-fast，不允許 runtime 猜測補洞

## 舊文件

repo 內仍保留較早期的 cutover、sandbox、MCP、policy、UI refactor 文件。若你在追歷史脈絡，可從 [docs](D:/PycharmProjects/Amon/docs) 往下查；若你要的是目前 vNext 入口，優先看本 README 與上方文件地圖。
