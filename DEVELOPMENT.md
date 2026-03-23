# 開發環境快速上手（本機）

以下步驟以 macOS/Linux 為例，Windows 可用 WSL 或等效指令。

## Agent 任務執行流程（必遵守）

1. 接到任何人類委託後，先拆解具體步驟並建立 TODO list。
2. TODO list 完成前不得直接進入開發或修改程式碼。
3. 開發時遵循下列修改原則。

### **修改原則**
  若是對既有專案做修改，理解此次改動的關鍵目的，在完成此目的的前提下：
  - 只能改動與bug或重構直接相關的區塊
  - 不得改變任何對外可觀察行為（characterization/contract tests 必須全過）
  - 除非特別要求指定，儘量不破壞原有 API / 資料結構 / 前端路由。
  - 不要把整個架構翻掉，除非使用者明說要重構或換技術。
4. 完成後需執行最小品質門檻與測試，並記錄結果。

### TODO list 建議格式

```markdown
- [ ] 釐清需求與影響範圍
- [ ] 依修改原則實作必要變更
- [ ] 執行 `python -m compileall src tests`
- [ ] 執行 `python -m unittest discover -s tests`
- [ ] 更新文件與提交紀錄
```

## 1) 安裝與初始化
```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

若只需最小依賴：
```bash
pip install -r requirements.txt
```

> 模型金鑰需放在環境變數中（例如 `OPENAI_API_KEY`）。

## 2) Lint / 最小品質門檻
```bash
python -m compileall src tests
```

## 3) 測試
```bash
python -m unittest discover -s tests
```

> 若測試涉及外部模型連線，請先設定對應的環境變數與可用的網路/Proxy。

## 4) 執行 CLI
```bash
amon init
amon project list
```

## vNext 文件維護

當調整 manifest / binder / compiler / runtime_vnext / templates 相關程式時，需同步檢查：

- `SPEC_v1.2.2.md`
- `docs/migration_manifest_v1.md`
- `docs/runtime_vnext.md`
- `docs/template_authoring.md`
- `docs/tool_policy.md`

並確認沒有把 inline runtime payload、preset-specific runtime branch、或 trigger bypass path 重新引回主路徑。

## vNext Stage 0 骨架

目前 repo 已預留 vNext 平行結構，但尚未接管 production runtime：

```text
src/amon/application/
src/amon/config/feature_flags.py
src/amon/domain/
src/amon/interfaces/api/
src/amon/interfaces/cli/
src/amon/runtime_vnext/
src/amon/storage/
src/amon/templates/
```

Feature flags 皆由環境變數控制，預設值如下：

```text
AMON_VNEXT_MANIFEST=0
AMON_VNEXT_BINDER=0
AMON_VNEXT_RUNTIME=0
AMON_VNEXT_UI=0
```

最小驗證指令：

```bash
python -m unittest tests.unit.test_feature_flags
python -m unittest tests.smoke.test_vnext_imports
```

## 5) 啟動 UI（預覽）
```bash
amon ui --port 8000
```
目前此命令在 repo 現況下可能立即結束；啟動路徑與限制請先看 `docs/known_limits.md`。
