# 使用情境決策樹與 AGENTS 組裝規則

這一層處理的是「這個專案要多黑盒、要多穩、要多工程化」，不是技術棧。

先判斷使用情境，再做 APSM 技術選型。不要直接從 React / FastAPI / monorepo 倒推專案應該長什麼樣子。

## 目的

1. 先用少量問題判斷專案的交付摩擦、維護強度與相容性要求。
2. 把結果寫成 machine-readable 的 `usage_scene` 與 `project_profile`。
3. 依此生成根目錄 `AGENTS.md`，再疊加 APSM 的技術補充規則。

> 注意：這裡的場景 A/B/C/D，和 APSM 的 A1/B3/C2 不是同一套編碼。前者是使用情境，後者是技術模板。

## 先判斷四個問題

這四個問題就是四個判定軸，也就是 `project_profile` 的四個欄位；`SKILL.md` 若用白話描述，仍以這裡的欄位名稱、值域與判定規則為單一真相來源。

如果需求敘述已經夠清楚，直接推定；只有在資訊不足且會影響場景分類時才反問使用者。

### Q1. 使用者是誰

- `personal`：個人、自用
- `small_team`：少量團隊、少量共用
- `internal_team`：持續內部使用
- `engineer_maintained`：工程師維護、會交接給工程師

### Q2. 使用週期多長

- `one_off`：一次性
- `occasional`：偶爾使用
- `long_term`：長期使用

### Q3. 修改頻率多高

- `rare`：幾乎不改
- `occasional`：偶爾改
- `continuous`：持續演進

### Q4. 壞掉代價多高

- `manual_redo_ok`：可接受手動重做
- `multi_user_disruption`：會造成多人困擾
- `workflow_blocking`：會阻斷工作流程

## 場景決策順序

依序判斷，不要自由發揮。

1. 若 `user_type = engineer_maintained`，進入場景 D。
2. 否則，若 `usage_duration = long_term` 且符合下列任一條件，進入場景 C。
   - `change_frequency = continuous`
   - `user_type = internal_team`
   - `failure_cost = workflow_blocking`
3. 否則，若同時符合下列條件，進入場景 A。
   - `user_type = personal`
   - `usage_duration != long_term`
   - `change_frequency != continuous`
   - `failure_cost = manual_redo_ok`
4. 其餘情況一律進入場景 B。

### 預設 fallback

資訊不足時，預設 `scene_b_shared_tool`，不要預設 A。

原因：
- 比個人黑盒工具更穩健
- 比長期內部工具更輕
- 對大多數真實需求更通用

## 四種使用情境

### 場景 A：`scene_a_personal_blackbox`

適用：
- 個人自用
- 快速交付
- 能立刻用比工程美感更重要

重點：
- 雙擊即跑
- 最少依賴
- 單體優先
- 文件以操作說明為主

限制：
- 不要為未來假設先拆太多層
- 不要先做前後端分離
- 不要加入非必要權限、角色、部署概念

### 場景 B：`scene_b_shared_tool`

適用：
- 少量人偶爾共用
- 不是正式產品，但不能太脆弱

重點：
- 仍然一鍵啟動
- log 與錯誤回報要完整
- 設定檔與資料格式穩定
- README 要含操作與常見問題

限制：
- 不要把關鍵操作藏深
- 不要依賴使用者懂命令列或環境變數

### 場景 C：`scene_c_internal_tool`

適用：
- 長期內部使用
- 會反覆修改
- 工作流程會依賴這個工具

重點：
- 最小改動
- 明確分層
- 向下相容
- 測試、文件、資料模型要穩

限制：
- 不要為了看起來整潔就整體重構
- 不要任意改函式名稱、欄位名、路徑

### 場景 D：`scene_d_engineer_maintained`

適用：
- 工程師接手維護
- 持續擴充
- 使用者與維護者分離

重點：
- 可讀性
- 可測試性
- 模組邊界清楚
- 文件要寫設計意圖

限制：
- 不要只顧能跑就把所有邏輯塞進入口檔
- 不要只留下終端使用者 README

## `project.config.json` 輸出格式

在 APSM 欄位之外，新增下列欄位：

```json
{
  "name": "my-vibe-app",
  "usage_scene": "scene_b_shared_tool",
  "project_profile": {
    "user_type": "small_team",
    "usage_duration": "occasional",
    "change_frequency": "occasional",
    "failure_cost": "multi_user_disruption"
  },
  "apsm_version": "1.0",
  "archetype": "web_app",
  "architecture": "separated",
  "frontend": "node_spa",
  "backend": "python_api",
  "version": "0.1.0"
}
```

## AGENTS.md 組裝規則

`AGENTS.md = 核心規則 + 使用情境規則 + 技術補充規則 + 專案特例`

### 1. 核心規則

永遠存在：
- 非開發者視角
- Windows 10/11 優先
- 雙擊 `run_app.bat` / `run_app.command` / `run_app.sh`
- 不把技術問題丟給使用者
- 修改採最小改動
- 預設保留狀態與完整 CRUD
- 最終交付 ZIP

### 2. 使用情境規則

依 `usage_scene` 擇一套用：
- `scene_a_personal_blackbox`
- `scene_b_shared_tool`
- `scene_c_internal_tool`
- `scene_d_engineer_maintained`

這一層決定：
- 要多黑盒
- 要多穩定
- 要多工程化
- 文件與測試要求高低
- 向下相容要求強度

### 3. 技術補充規則

依 APSM 組合補充：
- 單體 Python 模板
- 前後端分離 SPA/API
- monorepo
- Node SSR fullstack
- API-only service

### 4. 專案特例

只放本專案獨有要求，例如：
- 必須讀 Excel
- 必須本地儲存
- 必須使用 OpenAI Responses API
- UI 要對齊提供的 mockup
- 匯出格式不可變更

## 建議的 AGENTS.md 骨架

```md
# AGENTS.md

## 1. 專案定位
- 本專案目標
- 使用者是誰
- 維護者是誰
- 使用情境場景

## 2. 本專案最高原則
- 零摩擦
- Windows 優先
- 雙擊即可啟動
- 不要求使用者操作命令列
- 修改採最小改動

## 3. 目錄與檔案規範
- 根目錄固定檔案
- 各資料夾責任
- 不可任意改動的路徑或檔名

## 4. 實作規範
- 技術棧
- 狀態保存方式
- 設定檔位置
- 路徑處理方式
- logging 與錯誤處理

## 5. UI / UX 規範
- 介面語言
- 主要版面
- 核心功能位置
- 預覽與 CRUD 要求

## 6. 修改規範
- 最小修改
- 向下相容
- 不可隨意改動的穩定介面
- 哪些改動要同步更新 README / todo / 測試

## 7. 測試與打包規範
- 必要測試範圍
- 打包前檢查
- 必跑 `project_launcher.py`
- 最後交付 ZIP

## 8. 專案特例
- 本專案額外限制
- 本專案額外需求
```

## 交付要求

新專案落地時至少要做到：
- `specs/requirements.md` 已整理需求與假設
- `project.config.json` 已寫入 `usage_scene` 與 `project_profile`
- 根目錄存在 `AGENTS.md`
- 再根據 APSM 技術選型產生目錄結構
