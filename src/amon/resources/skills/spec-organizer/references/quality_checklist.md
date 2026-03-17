# Quality checklist

在交付或發版前，用這份清單檢查這個 skill 產生的規格是否真的可用。

## 1) Final output shape

- [ ] 第一行是 `# 規格整理 v 1.2.0`
- [ ] 最終輸出只包含 3 份交付物，沒有洩漏內部草稿與思考流程
- [ ] 在正式 spec 前，已先輸出研究與比較 code blocks
- [ ] 預設互動模式下，有等待使用者確認方向
- [ ] 若為單回合模式，研究與比較 code blocks 仍然先於最終 spec 出現
- [ ] 最終輸出不是只有標題的大綱
- [ ] 依序輸出：
  - [ ] `## 技術規格文件`
  - [ ] `## 非技術規格文件`
  - [ ] `## Web 版 Codex 分階段開發計畫`
- [ ] 若資訊不足，有先補問；若仍不足，合理假設有被明確標記

## 1.5) Research and alignment

- [ ] 有先查關鍵概念定義
- [ ] 有先查 1 個以上競品 / 類似服務
- [ ] 有先查 1 個以上相似 GitHub repo / 開源作法（若領域存在）
- [ ] 有整理差異、優劣與可借鏡處
- [ ] 有給出建議方案與待確認事項
- [ ] 有附來源與日期

## 2) Technical spec completeness

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

## 3) User spec plain-language check

- [ ] 白話版是寫給沒有開發經驗者
- [ ] 白話版每個章節都有具體內容，不是只有功能標題
- [ ] 沒有 API、DB、資料庫、後端、前端、schema、QPS、state machine、migration、cache、queue、cron、endpoint、token、WebSocket、CRUD 等技術詞
- [ ] 如果有提到內部能力，一律改寫成使用者可感知的行為
- [ ] 有說明能做什麼、怎麼做、限制是什麼、會看到什麼
- [ ] 有列出畫面提示語與常見錯誤提示語
- [ ] 有 UI 色彩描述與畫面示意 SVG
- [ ] 若輸出落檔，可執行 `python scripts/check_plain_language.py <path>` 並通過

## 4) G1 implementation consistency

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
- [ ] 若流程有階段性，已明確拆成 tabs、wizard、step navigation 或同頁分段顯示
- [ ] 每個主要畫面只有 1 個明確視覺重點
- [ ] 主要操作可在單一可視畫面內完成，沒有把重要功能推到過長頁面之外
- [ ] 沒有意義不明的控制項
- [ ] 有 UI 狀態保存，也有重新開始機制

## 5) Web Codex stage plan quality

- [ ] Stage 0 存在
- [ ] 每個 Stage 都有實質內容，不是只列欄位名
- [ ] Stage 0 含專案骨架、模組切分、lint/format、測試框架、env 樣板、README、storage 層與 migration/seed 策略
- [ ] 中間 stages 以 vertical slice 切分，不是單純前後端分工
- [ ] 每個 Stage 都有：
  - [ ] 動詞開頭的名稱
  - [ ] 目標
  - [ ] 前置條件
  - [ ] `Codex Web Instructions` code block
  - [ ] 風險與回滾方式
- [ ] 每個 `Codex Web Instructions` code block 都有：
  - [ ] 任務範圍
  - [ ] 檔案清單
  - [ ] 具體步驟
  - [ ] 輸出格式要求
  - [ ] 測試要求
  - [ ] 驗收標準（DoD）
  - [ ] 若涉及 LLM，明寫 Streaming
- [ ] 倒數第 2 Stage 是整合/回歸/邊界測試補齊
- [ ] 最終 Stage 是文件化與交付

## 6) Evidence and freshness

- [ ] 會影響規格的時效性資訊有先查證
- [ ] 查證內容有附來源與日期
- [ ] 無法確認的地方已標成風險或假設
