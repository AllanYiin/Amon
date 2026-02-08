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
amon config set providers.openai.model '"gpt-4o-mini"'
amon config get amon.provider --project <project_id>
amon config set amon.provider '"openai"' --project <project_id>

# 掃描技能索引
amon skills scan

# 單一模式執行
amon run --prompt "請用繁體中文摘要以下內容..." --project <project_id>

# 列出 MCP server 設定
amon mcp list

# 列出 MCP tools（使用快取）
amon tools mcp-list

# 重新抓取 MCP tools
amon tools mcp-list --refresh

# 呼叫 MCP tool
amon tools mcp-call local-tools:echo --args '{"text":"hello"}'

# 啟動 UI 預覽（瀏覽 http://localhost:8000）
amon ui --port 8000
```

> 提醒：模型金鑰需放在環境變數中（例如 `OPENAI_API_KEY`）。  

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
    model: gpt-4o-mini
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
