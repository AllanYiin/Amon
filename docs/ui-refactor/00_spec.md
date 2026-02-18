# UI 重構規格與對照表（Amon）

> 目的：建立「可重構、可驗收、不可硬抄」的共同依據，讓後續 UI 改版在不破壞現有互動契約（route / DOM id / API）的前提下進行。

## 1) 參考 UI 對照表（附件頁面資料夾 → Amon route/view）

> 規則：附件頁面僅作為「視覺與資訊架構參考」，不可直接照抄其 DOM 結構與 class 命名。

| 附件頁面資料夾 | Amon Shell Route（hash） | Amon View（data-shell-view） | 對應主容器 id | 備註 |
|---|---|---|---|---|
| `chat/` | `#/chat` | `chat` | `chat-layout` | 主對話頁（timeline、input、plan card、附件）。 |
| `context/` | `#/context` | `context` | `context-page` | 專案情境與草稿操作區。 |
| `billing/` | `#/billing` | `bill` | `bill-page` | 費用 KPI、趨勢圖、budget 與 breakdown。 |
| `logs/` | `#/logs` | `logs-events` | `logs-events-page` | Logs / Events 查詢與分頁。 |
| `tools/` | `#/tools` | `tools-skills` | `tools-skills-page` | Tools/Skills 清單與觸發預覽。 |
| `graph/` | `#/graph` | `graph` | `graph-page` | Mermaid / node inspector / run 選擇。 |
| `settings/` | `#/config` | `config` | `config-page` | 設定檢視（Global/Project/Effective）。 |

### Route/View 對齊原則

1. 不新增平行路由（例如 `#/settings`）去取代既有 `#/config`；以既有 route 契約為準。  
2. 若需改文案（例如「設定」顯示為 Settings），僅改顯示文字，不改 route 與 view key。  
3. 導覽切換應維持 `data-shell-view` 與主容器 id 的一對一對應。

## 2) DOM 不可更動項目（id 清單）

> 下列 id 直接由 `src/amon/ui/static/js/store/elements.js` 的 `collectElements()` 收斂，屬於前端互動與資料綁定契約。  
> **禁止變更**：`id` 名稱、刪除節點、改為重複 id。  
> **可調整**：結構層級、樣式 class、元件包裝層（前提是不影響 id 可被唯一選取）。

```text
project-select
timeline
execution-accordion
chat-form
chat-input
chat-attachments
attachment-preview
toast
confirm-modal
plan-card
plan-content
plan-commands
plan-patches
plan-risk
plan-confirm
plan-cancel
refresh-context
graph-preview
graph-code
graph-node-list
graph-run-meta
graph-run-select
graph-history-refresh
copy-run-id
graph-create-template
graph-node-drawer
graph-node-close
graph-node-title
graph-node-meta
graph-node-inputs
graph-node-outputs
graph-node-events
graph-parametrize
chat-project-label
context-project
context-overview
inspector-execution
inspector-thinking
inspector-artifacts
stream-progress
chat-layout
context-page
graph-page
ui-shell
toggle-sidebar
toggle-context-panel
context-panel
context-resizer
shell-run-status
shell-daemon-status
shell-budget-status
card-run-progress
card-billing
card-pending-confirmations
thinking-mode
thinking-summary
thinking-detail
artifacts-overview
artifacts-inspector-list
artifacts-empty
artifacts-go-run
artifacts-go-logs
artifacts-download-chat
artifact-preview-modal
artifact-preview-title
artifact-preview-body
artifact-preview-close
artifact-preview-download
artifact-preview-copy
tools-skills-page
bill-page
bill-refresh
bill-today
bill-project-total
bill-mode-summary
bill-current-run
bill-run-chart
bill-budgets
bill-exceeded
bill-breakdown-provider
bill-breakdown-model
bill-breakdown-agent
bill-breakdown-node
tools-skills-refresh
tools-list
skills-list
skills-collisions
skill-trigger-select
skill-trigger-preview
skill-injection-preview
config-page
logs-events-page
docs-page
docs-refresh
docs-tree-meta
docs-filter
docs-tree-viewport
docs-preview-title
docs-preview-meta
docs-preview-content
docs-open
docs-download
docs-insert
logs-source
logs-time-from
logs-time-to
logs-filter-project
logs-filter-run
logs-filter-node
logs-filter-severity
logs-filter-component
logs-refresh
logs-download
logs-summary
logs-list
logs-prev
logs-next
logs-page-label
events-filter-type
events-time-from
events-time-to
events-filter-project
events-filter-run
events-filter-node
events-refresh
events-summary
events-list
events-prev
events-next
events-page-label
config-refresh
config-search
config-export
config-global
config-project
config-effective-summary
config-table-body
context-draft-input
context-draft-meta
context-save-draft
context-import-file
context-extract-chat
context-clear-chat
context-clear-project
```

## 3) Design Tokens 草案（色彩/字級/間距/圓角/陰影）

> 先抽象成 token，再由元件 consume；避免在頁面直接 hard code 色碼/陰影/間距。

### 3.1 色彩（Color）
- `--color-bg-app`：整體背景
- `--color-bg-surface-1`：主卡片背景
- `--color-bg-surface-2`：次卡片/面板背景
- `--color-fg-primary`：主要文字
- `--color-fg-secondary`：次要文字
- `--color-border-default`：一般邊框
- `--color-border-strong`：強調邊框
- `--color-brand-primary`：品牌主色（按鈕/連結）
- `--color-brand-primary-hover`
- `--color-success` / `--color-warning` / `--color-danger` / `--color-info`
- `--color-overlay`：modal/backdrop

### 3.2 字級（Typography）
- `--font-family-base`
- `--font-size-xs/sm/md/lg/xl/2xl`
- `--font-weight-regular/medium/semibold/bold`
- `--line-height-tight/normal/relaxed`

### 3.3 間距（Spacing）
- `--space-0/1/2/3/4/5/6/8/10/12/16`
- `--layout-gutter`
- `--panel-gap`

### 3.4 圓角（Radius）
- `--radius-sm/md/lg/xl/full`

### 3.5 陰影（Shadow）
- `--shadow-xs/sm/md/lg`
- `--shadow-focus`（focus ring + elev）

### 3.6 動畫與狀態（可選）
- `--duration-fast/base/slow`
- `--ease-standard`
- `--opacity-disabled`

## 4) 共用元件清單（首批抽取）

> 命名以語意為主，不與特定 CSS framework 綁死。

1. **Card**：標準容器（header/body/footer variants）
2. **Pill**：狀態標籤（run/daemon/budget）
3. **Segmented**：tab/section 切換（Thinking / Execution / Artifacts）
4. **Chip**：篩選與輕量標記（logs/events filter tag）
5. **Toggle**：開關控制（側欄、context panel、mode）
6. **ListRow**：清單列（logs/events/docs/tools）
7. **BottomNav**：行動版底部導覽（對應 shell-nav）
8. **Timeline**：聊天/執行事件時間軸
9. **NodeCard**：graph node 詳細資訊卡
10. **Modal**：確認與預覽（confirm / artifact preview）
11. **EmptyState**：空狀態 + 引導按鈕
12. **Toolbar**：搜尋/篩選/刷新操作列
13. **StatCard**：KPI 類資訊卡（billing / run progress）
14. **DataTable**：設定與明細表格（config/logs）

### 禁止事項（Anti-copy）

- 禁止直接複製 Tailwind demo 的 DOM 樹（包含巢狀層級與語意不符標籤）。
- 禁止整段搬運 Tailwind utility class 字串作為正式實作。
- 禁止以 `div soup` 方式重建，必須維持語意化標籤與可及性（`header/nav/main/section/button/label`）。
- 可參考視覺層次與版面比例，但需改寫為 Amon 自有語意結構 + token + 共用元件。

## 5) Done 定義（手動回歸測試點檢清單）

> 每次 UI 重構 PR 至少完成下列手動檢查，並在 PR Validation 區塊附結果。

### 5.1 Route / View 切換
- [ ] `#/chat` / `#/context` / `#/graph` / `#/tools` / `#/logs` / `#/billing` / `#/config` 都可進入。
- [ ] 側欄 active 狀態與目前 view 一致。
- [ ] 切換頁面不會遺失 project selector 狀態。

### 5.2 DOM 契約
- [ ] `collectElements()` 清單中的 id 全部仍可唯一選取。
- [ ] 無重複 id。
- [ ] 既有事件（送出訊息、刷新、下載、分頁）可正常觸發。

### 5.3 互動/可用性
- [ ] Chat streaming 過程有進度回饋且 UI 不鎖死。
- [ ] Plan Card 可正常顯示、確認、取消。
- [ ] Graph preview / node drawer / run selector 正常。
- [ ] Billing、Logs、Tools、Config 各頁刷新按鈕可用。

### 5.4 響應式與可及性
- [ ] 桌面/窄版下側欄與 context panel 可操作。
- [ ] 鍵盤可聚焦主要互動元素。
- [ ] 文字對比與狀態顏色可辨識。

### 5.5 規範遵循
- [ ] 無 hard coding 色碼/間距（改用 tokens）。
- [ ] 無直接照抄 Tailwind demo DOM/class。
- [ ] 不新增與既有契約衝突的 route、id、API 路徑。
