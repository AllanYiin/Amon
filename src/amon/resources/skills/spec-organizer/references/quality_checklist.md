# Quality checklist

這份 checklist 用來記錄 spec-organizer 目前是否符合 `skill-creator-advanced` 的 readiness gate 規範。
本次 audit 以 `quick_validate.py`、`format_check.py`、`audit_skill_references.py` 與 `SKILL.md` 結構掃描為基礎，並保留 skill 專屬檢核項。

## Final gate
- Audit date: 2026-03-24
- Compliance level: 高
- Overall status: PASS
- Automated checks:
  - [x] `quick_validate.py` passed
  - [x] `format_check.py` passed
  - [x] `audit_skill_references.py` passed
- Key observations:
  - 自動檢查全數通過。
  - 本次將舊 checklist 升級為 readiness gate 結構。
- Structural gaps to keep improving:
  - 缺少明確 role 區塊
  - 缺少明確 decision boundary 區塊
  - 缺少 worked examples / examples 區塊

## Format checks
- [x] skill folder 名稱符合 kebab-case
- [x] `SKILL.md` 存在且通過基本 frontmatter 驗證
- [x] `format_check.py` 為 0 errors / 0 warnings
- [x] `SKILL.md` 內提到的本地 `scripts/`、`references/`、`assets/` 路徑都存在
- [x] `references/quality_checklist.md` 已存在且已依本次 audit 更新
- [x] `SKILL.md` 中沒有待清理的 `TODO` / `[TODO]`

## Requirement and policy checks
- [x] `SKILL.md` 有明確 workflow / instructions
- [ ] 有獨立 `role` 區塊或等價角色定義
- [ ] 有獨立 decision boundary 區塊或等價使用邊界
- [x] 有明確 output contract / output shape 要求
- [x] 有明確 default follow-through policy / ask-first 邊界
- [x] 有工具或路由使用規則
- [ ] 有 worked examples / examples 支撐輸出品質

## Common error checks
- [x] 沒有失效的本地引用路徑
- [x] frontmatter / 命名 / description 沒有被 validator 擋下
- [x] 結構與文字格式沒有被 linter 擋下
- [ ] readiness gate 所期待的關鍵區塊已完整具備
- [x] checklist 已與新版 readiness gate 結構對齊

## Skill-specific checks
在交付或發版前，用這份清單檢查這個 skill 產生的規格是否真的可用。

### 1) Final output shape

- [ ] 第一行是 `# 規格整理 v 1.2.0`
- [ ] 最終輸出只包含 3 份交付物，沒有洩漏內部草稿與思考流程
- [ ] 在正式 spec 前，已先輸出研究與比較 code blocks
- [ ] 預設互動模式下，有等待使用者確認方向
- [ ] 若為單回合模式，研究與比較 code blocks 仍然先於最終 spec 出現
- [ ] 最終輸出不是只有標題的大綱
- [ ] 依序輸出：
  - [ ] `## 技術規格文件`
  - [ ] `## 非技術規格文件`
  - [ ] `## Codex / Claude Code 分階段開發計畫`
- [ ] 若資訊不足，有先補問；若仍不足，合理假設有被明確標記

### 1.5) Research and alignment

- [ ] 有先查關鍵概念定義
- [ ] 有先查 1 個以上競品 / 類似服務
- [ ] 有先查 1 個以上相似 GitHub repo / 開源作法（若領域存在）
- [ ] 有整理差異、優劣與可借鏡處
- [ ] 有給出建議方案與待確認事項
- [ ] 有附來源與日期

### 2) Technical spec completeness

- [ ] 每個主要章節都有實質內容，不是只有標題
- [ ] 每個主要章節至少有段落、表格、規則或欄位定義
- [ ] 專案目錄規劃包含目錄樹、責任、代表檔案與命名原則
- [ ] 背景 / 目標 / 範圍 / 不做什麼
- [ ] Persona
- [ ] 系統說明
- [ ] 核心流程設計
- [ ] 開發應注意重點以及應避開誤區
- [ ] UI 風格定調與色彩策略
- [ ] 專案目錄規劃
- [ ] 前後端模組說明
- [ ] 架構 SVG
- [ ] 任務模型與資訊優先級
- [ ] 狀態模型與揭露策略
- [ ] 資訊架構表
- [ ] 使用流程
- [ ] 功能清單（含 CRUD 與狀態）
- [ ] G3M
- [ ] UI 設計（含色彩規範）
- [ ] UI 元件清單
- [ ] 分步導覽策略
- [ ] UI layout SVG
- [ ] 非功能需求
- [ ] 核心資料模型
- [ ] State 管理與持久化
- [ ] API 設計
- [ ] 錯誤處理 / 回退策略 / 可觀測性
- [ ] 狀態機
- [ ] 通知與背景執行
- [ ] UI 事件回報
- [ ] UI ↔ API Mapping
- [ ] UI 狀態保存與重新開始
- [ ] 建議補充的功能
- [ ] 驗收條件
- [ ] 測試案例
- [ ] Edge / Abuse cases

### 3) User spec plain-language check

- [ ] 白話版是寫給沒有開發經驗者
- [ ] 白話版每個章節都有具體內容，不是只有功能標題
- [ ] 沒有 API、DB、資料庫、後端、前端、schema、QPS、state machine、migration、cache、queue、cron、endpoint、token、WebSocket、CRUD 等技術詞
- [ ] 如果有提到內部能力，一律改寫成使用者可感知的行為
- [ ] 有說明能做什麼、怎麼做、限制是什麼、會看到什麼
- [ ] 有列出畫面提示語與常見錯誤提示語
- [ ] 有 UI 色彩描述與畫面示意 SVG
- [ ] 若輸出落檔，可執行 `python scripts/check_plain_language.py <path>` 並通過

### 4) G1 implementation consistency

- [ ] 每個新增物件都有 Update / Delete
- [ ] 每個物件都有 state 變化說明
- [ ] 有 state 管理與持久化設計
- [ ] 支援「以專案形式開啟並繼續編輯」
- [ ] 所有上傳功能都有預覽能力
- [ ] 所有縮放規則都維持原始寬高比
- [ ] 所有 LLM 輸出都明確要求 Streaming
- [ ] 模組化、穩定介面、最小改動原則有被體現
- [ ] 通知與背景執行有定義觸發條件、狀態流轉、去重、取消、重試與失敗告警
- [ ] 可觀測性至少定義 logs、metrics、traces 或等價監測方案
- [ ] UI 事件回報能支撐追錯、稽核或行為分析
- [ ] 專案目錄規劃與模組邊界、測試位置、設定位置彼此一致
- [ ] 已先定調 UI 風格，再決定配色
- [ ] 已定義 2-3 種主色/輔色與 1 種強調色
- [ ] 若是工作台或流程型 UI，已定義唯一 primary task
- [ ] 若是工作台或流程型 UI，task model 已拆成唯一主目標 / 次目標 / 低頻目標 / 罕見目標
- [ ] 若是工作台或流程型 UI，已定義 task model、state model、資訊分類與 visibility plan
- [ ] 若是工作台或流程型 UI，已定義資訊架構表（資訊項目 / 使用頻率 / 是否首屏必須 / 所屬任務階段 / 顯示條件 / 建議容器 / 是否可收合）
- [ ] 若是工作台或流程型 UI，state model 已對每個 state 定義進入條件 / 必顯資訊 / 隱藏資訊 / 主 CTA / 離開條件
- [ ] 若流程有階段性，已明確拆成 tabs、wizard、step navigation 或同頁分段顯示
- [ ] 每個主要畫面只有 1 個明確視覺重點
- [ ] 首屏至多 1 個主操作區、1 個狀態區、1 個次要摘要
- [ ] 首屏沒有超過 2-3 個主要視覺群組，且只有 1 個主 CTA
- [ ] `reference` 類資訊預設收合或延後揭露
- [ ] `exception-handling` 類資訊只在對應 state 顯示
- [ ] 相同任務流中的說明文字已優先內嵌在元件旁，而不是獨立大型說明卡
- [ ] 主要操作可在單一可視畫面內完成，沒有把重要功能推到過長頁面之外
- [ ] 沒有意義不明的控制項
- [ ] 有 UI 狀態保存，也有重新開始機制

### 5) Codex / Claude Code stage plan quality

- [ ] Stage 0 存在
- [ ] 每個 Stage 都有實質內容，不是只列欄位名
- [ ] Stage 0 含專案骨架、模組切分、lint/format、測試框架、env 樣板、README、storage 層與 migration/seed 策略
- [ ] 中間 stages 以 vertical slice 切分，不是單純前後端分工
- [ ] 每個 Stage 都有：
  - [ ] 動詞開頭的名稱
  - [ ] 目標
  - [ ] 前置條件
  - [ ] `Codex Instructions` code block
  - [ ] `Claude Code Instructions` code block
  - [ ] 風險與回滾方式
- [ ] 每個 `Codex Instructions` code block 都有：
  - [ ] 建議貼用方式
  - [ ] 任務範圍
  - [ ] 檔案清單
  - [ ] 具體步驟
  - [ ] 輸出格式要求
  - [ ] 測試要求
  - [ ] 驗收標準（DoD）
  - [ ] 若涉及 LLM，明寫 Streaming
- [ ] 每個 `Claude Code Instructions` code block 都有：
  - [ ] 建議貼用方式
  - [ ] 任務範圍
  - [ ] 檔案清單
  - [ ] 具體步驟
  - [ ] 輸出格式要求
  - [ ] 測試要求
  - [ ] 驗收標準（DoD）
  - [ ] 若涉及 LLM，明寫 Streaming
- [ ] Codex 版本若需要長期規則，有標示 `AGENTS.md` 的建議落點
- [ ] Claude Code 版本若需要長期規則，有標示 `CLAUDE.md` / `.claude/CLAUDE.md` 或 `.claude/skills/` / `.claude/commands/` 的建議落點
- [ ] 倒數第 2 Stage 是整合/回歸/邊界測試補齊
- [ ] 最終 Stage 是文件化與交付

### 6) Evidence and freshness

- [ ] 會影響規格的時效性資訊有先查證
- [ ] 查證內容有附來源與日期
- [ ] 無法確認的地方已標成風險或假設
