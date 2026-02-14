# Amon

* 規格整理：[`SPEC_v1.1.3.md`](SPEC_v1.1.3.md)

## CLI 快速開始

```bash
# 安裝套件
pip install -e .

# 初始化 Amon 資料夾（~/.amon）
amon init

# 建立專案
amon project create "2026Q1 市場研究"

# 列出專案
amon project list

# 更新專案名稱
amon project update <project_id> --name "新版專案名稱"

# 刪除（移至回收桶）與還原
amon project delete <project_id>
amon project restore <project_id>

# 讀寫設定（global 或專案）
amon config get providers.openai.model
amon config set providers.openai.model '"gpt-5.2"'
amon config get amon.provider --project <project_id>
amon config set amon.provider '"openai"' --project <project_id>
amon config show --project <project_id>

# 掃描技能索引
amon skills scan
amon skills list
amon skills show <skill_name>

# 單一模式執行
amon run --prompt "請用繁體中文摘要以下內容..." --project <project_id>

# 列出 MCP server 設定
amon mcp list
amon mcp allow local-tools:echo
amon mcp deny local-tools:echo

# 列出 MCP tools（使用快取）
amon tools mcp-list

# 重新抓取 MCP tools
amon tools mcp-list --refresh

# 呼叫 MCP tool
amon tools mcp-call local-tools:echo --args '{"text":"hello"}'

# 工具管理（legacy/native/builtin）
amon tools list
amon tools list --builtin
amon tools forge --project <project_id> --name "市場摘要" --spec "讀取資料並生成摘要"
amon tools test my_tool
amon tools register my_tool
amon tools run my_tool --args '{"input":"example"}'
amon tools call native:hello --args '{"name":"Amon"}'

# Toolforge（建立/安裝/驗證原生工具）
amon toolforge init my_tool
amon toolforge install ./my_tool
amon toolforge verify

# 啟動 UI 預覽（瀏覽 http://localhost:8000）
amon ui --port 8000

# 互動式 Chat
amon chat --project <project_id>

# 檔案安全操作
amon fs delete ./report.pdf
amon fs restore <trash_id>

# 匯出專案（zip）
amon export --project <project_id> --out ./export.zip

# 內建評測
amon eval --suite basic

# 系統診斷
amon doctor

# Graph 執行與模板
amon graph run --project <project_id> --graph ./graph.json
amon graph template create --project <project_id> --run <run_id>
amon graph template parametrize --template <template_id> --path "$.nodes[0].prompt" --var_name topic

# Hooks / Schedules / Jobs
amon hooks list
amon hooks add <hook_id> --file ./hook.yaml
amon hooks enable <hook_id>
amon hooks disable <hook_id>
amon hooks delete <hook_id>

amon schedules list
amon schedules add --payload '{"cron":"0 9 * * *","action":"graph.run","args":{"template_id":"daily"}}'
amon schedules run-now <schedule_id>
amon schedules enable <schedule_id>
amon schedules disable <schedule_id>
amon schedules delete <schedule_id>

amon jobs list
amon jobs start <job_id>
amon jobs stop <job_id>
amon jobs restart <job_id>
amon jobs status <job_id>

# 啟動常駐服務
amon daemon --tick-interval 5

# 使用外部 sandbox runner 執行程式
amon sandbox exec --language python --code-file ./script.py --in data/input.txt=./fixtures/input.txt --out-dir ./sandbox-out
```

> 提醒：模型金鑰需放在環境變數中（例如 `OPENAI_API_KEY`）。  

## 功能更新摘要

* 新增工具管理：支援 legacy 工具、toolforge 原生工具與內建工具的列出、呼叫與測試。
* 新增 Graph 執行與模板化能力，可用於重複任務與參數化流程。
* 新增 Hooks/Schedules/Jobs 與 daemon 常駐服務，支援事件觸發、排程與背景工作。
* 新增檔案安全操作、專案匯出、系統診斷與內建評測指令。

## 外部 Sandbox Runner 整合（shared runner）

詳細維運文件請見：`docs/sandbox_runner.md`（包含 threat model、限制清單、docker-compose 風險與錯誤排除）。

1. 安裝 runner 依賴並啟動：

```bash
pip install -e .[sandbox-runner]
amon-sandbox-runner
```

2. （可選）在 `~/.amon/config.yaml` 設定 runner 位址與金鑰環境變數：

```yaml
sandbox:
  runner:
    base_url: http://127.0.0.1:8088
    timeout_s: 30
    api_key_env: SANDBOX_RUNNER_API_KEY
```

3. 用 CLI 呼叫 runner `/run`：

```bash
amon sandbox exec \
  --language python \
  --code-file ./script.py \
  --in data/input.txt=./fixtures/input.txt \
  --out-dir ./sandbox-out
```

`--out-dir` 會把 runner 回傳的 `output_files`（base64）解碼落地，方便直接檢查輸出檔案。

## 目錄結構（~/.amon）

```
~/.amon/
├─ projects/        # 專案資料
├─ trash/           # 回收桶 + manifest.json
├─ logs/            # amon.log + billing.log
├─ cache/           # 索引快取
│  └─ mcp/          # MCP tools 快取
├─ skills/          # 全域 skills
├─ python_env/      # 共用 Python 環境
└─ node_env/        # 共用 Node 環境
```

## 設定檔與優先順序

* 全域設定：`~/.amon/config.yaml`
* 專案設定：`<project>/amon.project.yaml`

## MCP 行為補充

* MCP tools 清單預設會讀取 `~/.amon/cache/mcp/<server>.json` 快取，使用 `amon tools mcp-list --refresh` 強制重新抓取。
* 若設定 `mcp.allowed_tools`，僅允許清單內的工具被呼叫（格式支援 `server:tool` 或 `server.*`）。
* 優先順序：專案設定 > 全域設定 > 預設值

### 設定範例（節錄）

```yaml
amon:
  provider: openai
providers:
  openai:
    type: openai_compatible
    base_url: https://api.openai.com/v1
    model: gpt-5.2
    api_key_env: OPENAI_API_KEY
skills:
  global_dir: ~/.amon/skills
  project_dir_rel: .claude/skills
mcp:
  servers:
    local-tools:
      type: http
      endpoint: http://localhost:8080
  allowed_tools:
    - filesystem.read
```

## Skills 結構與掃描行為

* Skill 目錄：每個 skill 是一個資料夾，包含 `SKILL.md`。
* `SKILL.md` 需包含 YAML frontmatter，至少有 `name` 與 `description`。
* 可選擇建立 `references/` 目錄放補充檔案（掃描時只列出清單，不讀取大檔）。
* `amon skills scan` 會掃描全域與專案目錄並寫入快取索引：
  - 全域：`~/.amon/skills`
  - 專案：`<project>/.claude/skills`
  - 索引：`~/.amon/cache/skills/index.json`

範例：

```
<skill_dir>/
├─ SKILL.md
└─ references/
   └─ diagram.png
```

# Vibe Coding 開發規範

本專案遵循 Vibe Coding 的最小修改與安全開發原則，並以繁體中文與台灣用語為優先介面語系。
