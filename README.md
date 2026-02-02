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
```

> 提醒：模型金鑰需放在環境變數中（例如 `OPENAI_API_KEY`）。  

## 目錄結構（~/.amon）

```
~/.amon/
├─ projects/        # 專案資料
├─ trash/           # 回收桶 + manifest.json
├─ logs/            # amon.log + billing.log
├─ cache/           # 索引快取
├─ skills/          # 全域 skills
├─ python_env/      # 共用 Python 環境
└─ node_env/        # 共用 Node 環境
```

## 設定檔與優先順序

* 全域設定：`~/.amon/config.yaml`
* 專案設定：`<project>/amon.project.yaml`
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
