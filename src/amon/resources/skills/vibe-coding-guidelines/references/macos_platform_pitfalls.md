# macOS 平台常見錯誤與避雷

## 命名原則

- 主入口維持 `scripts/project_launcher.py`，因為它是跨平台總控器，不應為了文件分流而拆成 `project_launcher_macos.py`。
- 若要保留 POSIX 輔助入口，名稱應使用 `scripts/project_launcher_posix.py`；`project_launcher_linux.py` 只能作為相容別名。
- macOS 專屬說明應放在 `references/macos_platform_pitfalls.md`，避免把 Finder、Gatekeeper 與 Linux Shell 行為混在一起。

## 權限、Finder 與 Gatekeeper

- `run_app.command` 解壓後可能失去可執行權限；README 與 troubleshooting 至少要提供 `chmod +x run_app.command`。
- Finder 可以雙擊 `.command`，但 Gatekeeper 仍可能阻擋第一次啟動；README 應補充「到系統設定 > 隱私權與安全性允許開啟」的人話說明。
- `run_app.command` 本身也應直接輸出這段提示，不要把所有責任都丟給 README。
- 不要只寫「被 macOS 擋住」；應說清楚是系統安全機制首次攔截未簽署腳本。

## 路徑與檔名

- macOS 在不同磁碟格式下對大小寫敏感度可能不同，不能把目前機器的行為當成保證。
- 即使在大小寫不敏感磁碟上開發，也要用一致檔名，避免交付到 Linux 或大小寫敏感磁碟時失敗。
- 路徑處理優先用 `pathlib` / `os.path`。

## 啟動腳本

- `run_app.command` / `run_app.sh` 應使用 `#!/usr/bin/env bash` 與 LF 換行。
- 自動開瀏覽器時，macOS 優先 `open`，若失敗，再 fallback 到 `python -m webbrowser` 之類的方案。
- 若啟動器需要保留視窗與 log，應清楚說明終端機輸出位置，不要讓使用者誤以為「閃退」。

## Port 與前後端協調

- 不要只在啟動前掃描「看起來可用」的 port；若要做動態 port，應以服務實際綁定後的 port 為準。
- 若採固定 port 策略，衝突時要清楚提示被佔用的是哪個 port，以及使用者下一步該怎麼改。
- 若有前後端分離，前端 API base 與後端 port 來源要一致，避免前端還連舊 port。

## 匯入與執行模式

- `attempted relative import with no known parent package` 常出現在直接執行 `src/main.py`、`src/app.py`、`backend/main.py` 這類入口檔時。
- 優先解法是改成套件入口（例如 `python -m package.module`）；若要自動修復，至少要先備份原檔。

## 文件與交付

- README 應明寫 macOS 啟動方式、權限處理方式、Gatekeeper 提示與常見排除步驟。
- 若使用者是非技術背景，不要假設他知道 Finder 右鍵開啟、Gatekeeper、執行權限代表什麼。
