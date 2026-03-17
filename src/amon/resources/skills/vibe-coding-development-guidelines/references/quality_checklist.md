# 交付前 QA 清單（跨平台 Vibe Coding）

## 一鍵可跑（Zero Friction）
- [ ] 交付物為 ZIP；解壓縮後可直接點一下啟動：
  - Windows：雙擊 `run_app.bat`
  - macOS：雙擊 `run_app.command`（必要時先 `chmod +x run_app.command`）
  - Linux：雙擊/執行 `run_app.sh`（必要時先 `chmod +x run_app.sh`）
- [ ] `run_app.*` 會自動建立 `.venv/`、安裝 `requirements.txt`、執行自動檢查、啟動服務並（若可推斷 URL）自動開啟瀏覽器。
- [ ] 使用者不需要手動輸入任何指令，不需要安裝額外工具（除 Python/Node 必要條件外；且 README 有清楚連結與圖文引導）。

## 檔案與目錄規範
- [ ] `project.config.json` 存在，且包含 `usage_scene`、`project_profile`、`apsm_version`、`archetype`、`architecture`、`frontend`、`backend`、`version`。
- [ ] 根目錄存在：`specs/requirements.md`、`AGENTS.md`、`run_app.bat`、`run_app.command`、`run_app.sh`、`requirements.txt`、`README.md`、`todo.md`。
- [ ] 目標專案存在 `scripts/project_launcher.py`，且來源是此 skill 內的 `scripts/project_launcher.py`。
- [ ] 目標專案存在 `scripts/apsm_validate.py`，且可成功執行。
- [ ] 已執行過 `project_launcher.py` 的專案，存在 `.runtime/ports.json`、`.runtime/launcher_state.json` 與 `logs/launcher.log`。
- [ ] `.venv/` 位於根目錄且不納入 ZIP。
- [ ] `.env` 不進版控；`.env.example` 有範本（至少包含 host/port 與 API base）。
- [ ] `specs/requirements.md` 已寫入目前確認版規格，且不只是一個空殼檔案。
- [ ] `AGENTS.md` 已寫出專案定位、最高原則、使用情境規則、技術補充規則與專案特例。
- [ ] `README.md` 內含「最新目錄結構」段落（與實際一致）。
- [ ] `python scripts/apsm_validate.py --project <target-project> --strict` 已通過。

## Windows 相容性
- [ ] `.py/.json/.md/.html` 均為 UTF-8 無 BOM。
- [ ] `run_app.bat` 預設為 ASCII-only；未把 ANSI/CP950 當成規範，也未在沒有必要時預設加入 `chcp 65001`。
- [ ] Python 程式使用 `pathlib`/`os.path.join`；沒有硬寫 `\\`。
- [ ] `.bat` 未使用任何 Linux 指令（`ls/rm/cp/mv/export/pwd/touch` 等）。

## 錯誤處理與日誌
- [ ] 主入口有全域 `try/except`，不會閃退。
- [ ] UI 錯誤訊息為繁體中文、白話描述，並提示「請複製以下訊息給 AI 助手」。
- [ ] `logs/` 會寫入 stack trace 與詳細技術訊息。
- [ ] logs 不包含 API Key、密碼或敏感資料。
- [ ] 若使用 toast 顯示錯誤，內容可複製、停留時間足夠，不會一閃而過。

## Port 與啟動穩定性
- [ ] 若尚未做完整動態 port 協調，遇到 port 衝突時會提供可理解指引，而不是宣稱已自動遞補。
- [ ] 若支援動態 port，實際綁定後的 port 會同步到瀏覽器 URL、前端 API base、log 與 launcher 狀態。
- [ ] 若有前端：前端 port 與 API base 由根目錄 `.env` 統一維護。
- [ ] 只有在 URL 可推得且通過 readiness check 時才自動開瀏覽器；否則只顯示明確啟動資訊。
- [ ] 若為前後端分離，後端已設定 CORS，至少允許本機前端開發位址。

## 狀態保存（Persistence）
- [ ] 任何設定（例如輸出路徑、視窗大小、上次輸入）會自動保存到本地檔（例如 `config.json`），下次啟動會恢復。
- [ ] 任何清單/列表類資料（關鍵字、任務、模板）可在 UI 直接 CRUD，不需要使用者手動改 JSON。
- [ ] 若有使用 mock API / 假資料，README 或 UI 已明確揭露，不會讓使用者誤以為是真實資料流。

## AI 功能（若有）
- [ ] Chat 一律使用 OpenAI Responses API；輸出為 streaming。
- [ ] STT 優先 Whisper，失敗才用 Responses fallback。
- [ ] 圖像生成預設 Nano Banana 2 / Gemini 3.1 Flash Image；prompt 含 no-text guardrail。
- [ ] model 名稱與金鑰從 env/config 讀取，不硬編碼。
- [ ] 若需求包含本地模型/離線推論，已評估 ONNX + ONNX Runtime 是否可作為優先方案。

## UI 規格遵循
- [ ] 若使用者提供 SVG、mockup 或畫面規格，最終 UI 與原規格一致；若做不到，已先和使用者對齊取捨。

## 測試
- [ ] 至少一次「乾淨解壓→點一下啟動」驗證成功（Windows/macOS/Linux 各至少一次，或明確標註你實際驗證的平台）。
- [ ] 主要功能有單元測試（正常 + 邊界）。
