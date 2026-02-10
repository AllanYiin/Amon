# 開發環境快速上手（本機）

以下步驟以 macOS/Linux 為例，Windows 可用 WSL 或等效指令。

## Agent 任務執行流程（必遵守）

1. 接到任何人類委託後，先拆解具體步驟並建立 TODO list。
2. TODO list 完成前不得直接進入開發或修改程式碼。
3. 開發時採最小修改原則，避免不必要的架構變更。
4. 完成後需執行最小品質門檻與測試，並記錄結果。

### TODO list 建議格式

```markdown
- [ ] 釐清需求與影響範圍
- [ ] 實作最小必要變更
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

## 5) 啟動 UI（預覽）
```bash
amon ui --port 8000
```
瀏覽器開啟：`http://localhost:8000`
