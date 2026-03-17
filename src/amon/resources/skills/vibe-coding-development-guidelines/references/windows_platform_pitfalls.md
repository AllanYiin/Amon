\* \*\*Windows 專屬硬規則 (Strict Windows Rules)\*\*：

&nbsp; \* \*\*指令與路徑（生死線）\*\*：

&nbsp;     \* \*\*嚴禁 Linux 語法\*\*：禁止在 `.bat` 或 `subprocess` 中使用 `ls`, `cp`, `mv`, `rm`, `pwd`, `export`, `touch`。

&nbsp;     \* \*\*必須使用 Windows 語法\*\*：

&nbsp;         \* `ls` -\\> `dir`

&nbsp;         \* `cp` -\\> `copy` / `xcopy`

&nbsp;         \* `rm` -\\> `del`

&nbsp;         \* `rm -rf` -\\> `rmdir /s /q`

&nbsp;         \* `export` -\\> `set`

&nbsp;     \* \*\*路徑分隔符\*\*：在 Python 代碼中一律使用 `os.path.join` 或 `/` (Python 在 Windows 支援 `/`)，\*\*嚴禁手寫 `\\`\*\*（這是跳脫字元，極易出錯）。

&nbsp; \* \*\*編碼地獄規避 (Encoding)\*\*：

&nbsp;     \* \*\*程式碼 (.py, .js, .json, .html)\*\*：一律使用 \*\*UTF-8 (無 BOM)\*\*。禁止 `UTF-8-SIG`，因為 Node.js 或某些 Python 庫讀取設定檔時會因為 BOM 表頭而崩潰。

&nbsp;     \* \*\*批次檔 (.bat)\*\*：預設採 \*\*ASCII-only\*\*，不要把 `ANSI`/`CP950` 當成規範，也不要預設寫入 `chcp 65001`。如果一定要在 `.bat` 輸出非 ASCII（例如中文），才允許明確控管 cmd 的 code page（例如 `chcp 65001`）並測試不同 Windows 地區設定。

&nbsp;     \* \*\*讀寫檔案\*\*：Python `open()` 必須顯式指定 `encoding='utf-8'`，否則 Windows 預設會用 CP950 讀取導致錯誤。

\* \*\*Windows 特有陷阱規避\*\*：

&nbsp;   \* \*\*路徑長度限制\*\*：

&nbsp;       \* 盡量保持資料夾結構扁平，避免過深的巢狀目錄導致超過 Windows 260 字元限制。

&nbsp;   \* \*\*端口衝突 (Port Conflict)\*\*：

&nbsp;       \* 不要只在啟動前掃描一個「看起來空的」 port 後就假設它可用；這會有 race condition。

&nbsp;       \* 若要支援動態 port，應讓服務實際綁定可用 port，再回讀最終 port，並同步更新瀏覽器 URL、前端 API base、log 與啟動器狀態。

&nbsp;       \* 若還沒有做完整同步，就不要宣稱自動遞補；應清楚提示哪個 port 被佔用，以及下一步怎麼改。

&nbsp;   \* \*\*防毒軟體干擾\*\*：

&nbsp;       \* 生成的 `.bat` 或 `.exe` (若有打包) 可能會被 Windows Defender 阻擋。

&nbsp;       \* 在說明文件中提示使用者：「若 Windows 跳出保護提示，請點選『其他資訊』->『仍要執行』」。

