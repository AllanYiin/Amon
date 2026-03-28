# Linux 平台常見錯誤與避雷

## 命名原則

- 主入口維持 `scripts/project_launcher.py`，因為它負責跨平台高階分類、修復與 launcher 生成，不應拆成平台專屬名稱。
- 若要保留 POSIX 輔助入口，名稱應使用 `scripts/project_launcher_posix.py`，不要再用 `project_launcher_linux.py` 去涵蓋 macOS。
- Linux 專屬說明應放在 `references/linux_platform_pitfalls.md`，避免和 macOS Gatekeeper、Finder 雙擊語意混寫。

## 權限與雙擊啟動

- `run_app.sh` 解壓後可能失去可執行權限；README 與 troubleshooting 至少要提供 `chmod +x run_app.sh`。
- 使用者若從圖形介面雙擊 `.sh`，不同桌面環境可能表現不一致；README 應補一句「若雙擊沒有反應，請改在 Terminal 執行 `./run_app.sh`」。
- 對非技術背景使用者，不要只丟指令；要先說明「檔案目前沒有執行權限」。

## 路徑與檔名

- Linux 預設檔案系統大小寫敏感；`config.json`、`Config.json`、`CONFIG.json` 不是同一個檔案。
- 讀寫設定檔、資產檔、模板檔時，路徑大小寫必須一致。
- 路徑處理優先用 `pathlib` / `os.path`，不要依賴人工拼字串。

## 啟動腳本

- `run_app.sh` 應包含 shebang，例如 `#!/usr/bin/env bash`，並使用 LF 換行。
- Shell 腳本不要混入 `dir`、`set`、`start` 這類 Windows 指令。
- 自動開瀏覽器時，Linux 優先 `xdg-open`，若不可用，再 fallback 到 `python -m webbrowser` 之類的方案。
- 若是在 WSL 上，應優先考慮 Windows 端瀏覽器啟動策略，而不是先撞 Linux 桌面匯流排；同時保留 readiness probe 結果與 open log。
- 若要在背景執行服務，可用 `&` 或 `nohup`；但要同時考慮 PID 清理與 log 路徑。

## Port 與前後端協調

- 不要只在啟動前掃描「看起來可用」的 port；若要做動態 port，應以服務實際綁定後的 port 為準。
- 若採固定 port 策略，衝突時要清楚提示被佔用的是哪個 port，以及使用者下一步該怎麼改。
- 若有前後端分離，前端 API base 與後端 port 來源要一致，避免前端還連舊 port。

## 匯入與執行模式

- `attempted relative import with no known parent package` 常出現在直接執行 `src/main.py`、`src/app.py`、`backend/main.py` 這類入口檔時。
- 優先解法是改成套件入口（例如 `python -m package.module`）；若要自動修復，至少要先備份原檔。

## 文件與交付

- README 應明寫 Linux 啟動方式、權限處理方式、以及雙擊失敗時改用 Terminal 的方式。
- 若使用者是非技術背景，不要假設他知道 Terminal、執行權限、背景程序代表什麼。
