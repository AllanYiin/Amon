# Codex Cloud 可重現環境草稿（allanyiin/amon）

> 目的：提供下一階段可直接整理進 `AGENTS.md` 的執行規範。

## 1) 環境設定建議

### Setup strategy（先自動、失敗再 fallback）
1. 先執行自動相依安裝：
   ```bash
   ./scripts/codex_cloud_setup.sh
   ```
2. `scripts/codex_cloud_setup.sh` 會先跑 `pip install -e .`（或帶 `AMON_INSTALL_EXTRAS`），失敗時自動 fallback：
   - `pip install --upgrade pip setuptools wheel`
   - `pip install -r requirements.txt`
   - `pip install -e .`

### Maintenance strategy（每日/每次 PR）
```bash
./scripts/codex_cloud_maintenance.sh
```
會依序做：
- `python -m compileall src tests`
- `python -m unittest discover -s tests -p 'test_*.py'`
- `python -m pip check`

## 2) Agent phase 網路策略（預設 Off）

### 預設
- `network: off`（agent phase 預設不開外網）

### 僅必要時開啟（受限 allowlist）
- 僅允許下列目的地：
  - `pypi.org`
  - `files.pythonhosted.org`
- 僅允許 HTTP methods：`GET`, `HEAD`, `OPTIONS`
- 禁止 `POST/PUT/PATCH/DELETE`

### 啟用時機（建議）
- 初次安裝依賴、快取失效需要重新抓套件時才暫時開啟。
- 安裝完成後立即恢復 `network: off`。

## 3) 建議環境變數

```bash
# 避免寫入系統區，保持每次任務可重現
export AMON_DATA_DIR="${PWD}/.tmp/amon-data"

# 若有 LLM 測試需求，金鑰只放環境變數（不要落盤）
export OPENAI_API_KEY="<your-key>"

# 可選：安裝 sandbox runner 依賴
export AMON_INSTALL_EXTRAS="sandbox-runner"
```

## 4) lint / test / dev server 可執行檢查清單

```bash
# setup
./scripts/codex_cloud_setup.sh

# lint（最小品質門檻）
python -m compileall src tests

# test
python -m unittest discover -s tests -p 'test_*.py'

# format（目前 repo 未配置 black/ruff/prettier，維持 N/A）
python -m compileall src tests

# dev server
amon ui --port 8000
```

## 5) 可直接貼進 AGENTS.md 的草稿段落

```md
### Codex Cloud Environment (Draft)
- Setup: `./scripts/codex_cloud_setup.sh`（先 `pip install -e .`，失敗自動 fallback 到明確安裝步驟）。
- Maintenance: `./scripts/codex_cloud_maintenance.sh`（compileall + unittest + pip check）。
- Agent phase network: 預設 `Off`；必要時才開啟 allowlist（`pypi.org`, `files.pythonhosted.org`）且僅允許 `GET/HEAD/OPTIONS`。
- Env vars:
  - `AMON_DATA_DIR=${PWD}/.tmp/amon-data`
  - `OPENAI_API_KEY`（如需）
  - `AMON_INSTALL_EXTRAS=sandbox-runner`（可選）
- Runbook:
  - lint: `python -m compileall src tests`
  - test: `python -m unittest discover -s tests -p 'test_*.py'`
  - dev server: `amon ui --port 8000`
```
