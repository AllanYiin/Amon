# Codex 工作契約（Repo Root）

## 1) 依賴/測試/品質工具偵測摘要
- 依賴管理：`pyproject.toml`（setuptools）與 `requirements.txt`（PyYAML）。
- 測試框架：`unittest`（以 `python -m unittest discover -s tests` 執行）。
- Lint/Format：未看到 ruff/black/isort/flake8/mypy 設定；採用最小品質門檻（`compileall`）。

## 2) 必跑命令（CI/本地一致）
> 若命令失敗，需在 PR 說明中標註原因與輸出摘要。

### Lint / 最小品質門檻
```bash
python -m compileall src tests
```

### Tests
```bash
python -m unittest discover -s tests
```

> 若無法完整執行測試，至少保留 `compileall` 作為 smoke check。

## 3) PR 規範
請在 PR 描述中固定提供下列區塊：

### Summary
- 條列本次變更重點（最多 3 點）。

### Risk
- 變更風險說明（例如：低/中/高 + 影響範圍）。

### Validation
- 列出實際執行過的命令與結果（包含失敗或受限原因）。

範例：
```
Summary
- 新增 AGENTS.md 與 DEVELOPMENT.md

Risk
- Low（僅文件與規範）

Validation
- python -m compileall src tests
- python -m unittest discover -s tests (失敗：外部連線 403)
```

## 4) 安全規範（必遵守）
- 嚴禁將 API Key、Token、密碼等 secrets 提交到 repo。
- 禁止在紀錄/範例中包含敏感 payload（PII、憑證、內部 URL）。
- 避免使用隱藏 Unicode 或 bidi 控制字元（如有需要，請明示原因）。
- 所有金鑰應只放在環境變數（例如 `OPENAI_API_KEY`）。
