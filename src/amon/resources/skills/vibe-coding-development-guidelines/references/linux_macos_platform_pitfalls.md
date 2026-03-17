# Linux/macOS 平台總覽與導讀

這份文件保留作為相容導讀，不再承載所有細節。

## 命名原則

- 主入口維持 `scripts/project_launcher.py`，因為它是跨平台總控器，不應為了文件分流而改成平台後綴。
- POSIX 輔助入口改以 `scripts/project_launcher_posix.py` 為主；`scripts/project_launcher_linux.py` 只保留相容別名，避免把 macOS 誤掛在 Linux 名下。
- 平台專屬文件改拆成兩份，避免 Linux 與 macOS 的啟動語意混寫。

## 讀哪一份文件

- Linux 啟動、`xdg-open`、Shell 權限與 Terminal 流程：看 `references/linux_platform_pitfalls.md`
- macOS Finder、`.command`、Gatekeeper 與 `open`：看 `references/macos_platform_pitfalls.md`

## 共同原則

- `run_app.sh` / `run_app.command` 都應保留詳細 log，安裝或啟動失敗時不可直接閃退。
- 若要自動開瀏覽器，Linux 應優先 `xdg-open`，macOS 應優先 `open`，再 fallback 到 Python 方案。
- 若要自動修復 relative import，至少要先備份原檔。
