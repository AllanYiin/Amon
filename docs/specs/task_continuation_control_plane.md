# Amon 任務續跑控制面規格

> 狀態：**提案文件（控制面規格）**
>
> 目標：在不推翻既有 `TaskGraph3Runtime`、`daemon`、`scheduler`、`jobs runner` 對外行為的前提下，補上可持續推進任務的 durable control plane，避免任務因單點失敗、空白輸出、worker 消失或流程誤判而過早終止。

## 0. 問題定義

目前 Amon 已有 graph runtime、daemon tick、scheduler 與 job resident runner，但仍存在下列風險：

- 任務執行壽命過度依賴單次執行流程，缺少 task-level durable reconciliation。
- 單一節點失敗時，系統較容易直接結束整體 run，而不是先判斷可否修補、重試或等待外部條件。
- 當 graph 已有狀態流但沒有文字輸出時，系統容易被誤判為「沒有內容」而提早停止。
- 未來任務將不只單一執行緒，必須支援多任務平行，且不能把 UI 綁成執行所有權持有者。

本規格定義的不是「永遠活著的背景 thread」，而是「以持久化狀態為中心，透過事件驅動與週期性 reconcile 持續把未完成任務推進到下一個穩定狀態」的控制面。

## 1. 設計原則

1. **correctness 依賴 durable state，不依賴單一 thread/process 存活**
2. **UI 只負責觀察與操作，不負責擁有執行生命週期**
3. **正常推進以事件驅動為主，週期性掃描只負責補掃與救援**
4. **控制面預設 deterministic，不以 LLM 作為主判斷器**
5. **所有新增控制面機制都必須向前相容，不破壞既有 graph/runtime 對外 contract**
6. **節點失敗不等於任務失敗，需先經過 failure classification**
7. **任務若未完成，應維持在明確的可追蹤狀態，而不是靜默消失**

## 2. 現況盤點與最小入侵落點

### 2.1 既有能力

- daemon loop：`src/amon/daemon/runner.py`
- scheduler tick：`src/amon/scheduler/engine.py`
- resident job runner：`src/amon/jobs/runner.py`
- graph runtime：`src/amon/taskgraph3/runtime.py`
- graph run 結果與事件落盤：`.amon/runs/<run_id>/`

### 2.2 既有能力可借用處

- `daemon.run_daemon(...)` 已有常駐 tick loop，可承接 reconcile。
- `scheduler.tick(...)` 已有週期觸發與持久化更新模式，可沿用作為控制面掃描節奏。
- `jobs.runner` 已有 heartbeat 與狀態檔模式，可借鏡 lease/heartbeat 行為。
- `TaskGraph3Runtime` 已有 node status / events / state 落盤，可作為 execution plane 的觀測來源。

### 2.3 本規格不做的事

- 不把 `TaskGraph3Runtime` 直接改寫成外部 workflow engine clone。
- 不要求 UI thread 常駐持有任務。
- 不把所有控制判斷都交給 LLM。
- 不導入破壞性的大型架構翻修。

## 3. 核心概念

### 3.1 Desired state 與 current state

- `desired state`：此任務最終應達成的目標，以及目前應處於的控制面狀態。
- `current state`：實際落盤的 run/node/attempt/lease/repair 狀態。
- controller 的責任是持續比對兩者，若 current state 未收斂到 desired state，就決定下一步 action。

### 3.2 執行面與控制面分離

- execution plane：真正執行 graph node、tool、agent、sandbox 的地方。
- control plane：決定何時派工、何時重試、何時修補、何時等待、何時宣告終止。

### 3.3 Lease + heartbeat

- worker 在取得可執行工作時，拿到一段有限期 lease。
- worker 在 lease 存續期間必須 heartbeat。
- 若 lease 過期，表示控制面可以回收該工作並重新派發，不需依賴原本 worker 還活著。

### 3.4 Token 成本邊界

- heartbeat / reconcile / lease 檢查 / state persistence / queue dispatch **不是** LLM token 成本。
- 只有真的發出模型請求時才會消耗 token。
- 因此控制面必須預設 deterministic，避免每次 tick 都叫模型重新思考。

## 4. 目標與非目標

### 4.1 目標

- 任務在 worker crash、daemon 重啟、節點短暫失敗時，仍可被重新接續。
- 任務若沒有文字輸出，但仍有節點進度，系統不得誤判為空回覆後終止。
- 多任務平行時可由多個 worker/queue 處理，不鎖住 UI。
- 任務的 retry、repair、cooldown、escalation 有明確預算與上限。
- 任何終止都必須是顯式狀態，而不是靜默消失。

### 4.2 非目標

- 不保證所有失敗都可自動修復。
- 不把所有 planner 問題都延後到 runtime 自動補救。
- 不在本階段導入分散式 consensus 或跨機器強一致鎖。

## 5. Canonical 資料模型

控制面需新增或明確化下列 durable state。資料可先以 JSON 檔落於 `.amon/control/` 或 `.amon/runs/` 周邊，後續再視需要抽成 repository。

### 5.1 TaskRun

建議欄位：

| 欄位 | 型別 | 說明 |
|---|---|---|
| `task_run_id` | string | 控制面任務實例 id |
| `graph_run_id` | string\|null | 對應 graph run id，尚未建 run 時可為 null |
| `goal` | object | 任務目標摘要、輸入、成功條件 |
| `status` | enum | 見 6.1 |
| `desired_status` | enum | 例如 `active`、`paused`、`cancelled` |
| `active_worker_id` | string\|null | 目前持有 lease 的 worker |
| `lease_expires_at` | datetime\|null | 任務層 lease 過期時間 |
| `next_wake_at` | datetime\|null | 下次允許 reconcile 的時間 |
| `retry_budget` | int | 可重試次數上限 |
| `repair_budget` | int | 可自動修補次數上限 |
| `no_progress_deadline` | datetime\|null | 無進度超時點 |
| `last_progress_at` | datetime\|null | 最近一次可觀察進度 |
| `failure_class` | string\|null | 最近一次失敗分類 |
| `terminal_reason` | string\|null | 明確終止原因 |
| `created_at/updated_at` | datetime | 稽核用途 |

### 5.2 NodeRun

| 欄位 | 型別 | 說明 |
|---|---|---|
| `task_run_id` | string | 所屬任務 |
| `node_id` | string | graph node id |
| `status` | enum | `ready/running/waiting/retrying/succeeded/failed/skipped` |
| `attempt_count` | int | 已執行次數 |
| `last_error` | string\|null | 最近錯誤 |
| `lease_owner` | string\|null | 節點層 lease 持有者 |
| `lease_expires_at` | datetime\|null | 節點層 lease 到期時間 |
| `cooldown_until` | datetime\|null | 重試冷卻到期時間 |
| `last_progress_at` | datetime\|null | 最近節點進度時間 |

### 5.3 AttemptRecord

| 欄位 | 型別 | 說明 |
|---|---|---|
| `attempt_id` | string | 單次執行識別 |
| `task_run_id` | string | 所屬任務 |
| `node_id` | string\|null | 可為 task-level attempt |
| `attempt_type` | enum | `execute/retry/repair/replan` |
| `started_at/finished_at` | datetime | 執行時間 |
| `result` | enum | `succeeded/failed/aborted` |
| `error_class` | string\|null | 失敗分類 |
| `token_usage` | object\|null | 只有 LLM attempt 才需要 |
| `notes` | object | 額外診斷資料 |

## 6. 狀態機

### 6.1 TaskRun 狀態

`created -> queued -> dispatching -> running -> waiting_external -> retry_wait -> repairing -> replanning -> succeeded`

並支援：

- `paused`
- `failed_terminal`
- `cancelled`
- `abandoned`

說明：

- `running`：至少有一個 node 正在執行，或 execution plane 正在推進。
- `waiting_external`：等待使用者輸入、批准、外部 webhook、排程時間、資源釋放。
- `retry_wait`：可重試，但尚在 cooldown。
- `repairing`：由 deterministic repair 或有限次 LLM repair 在修補。
- `replanning`：原計畫已無法收斂，需重新規劃。
- `failed_terminal`：已判定無法安全自動前進。

### 6.2 狀態轉換原則

- 任何進入 terminal state 都必須帶 `terminal_reason`。
- 任何從 `running` 離開但任務未完成，都必須留下 `next_wake_at` 或明確等待條件。
- `waiting_external` 與 `retry_wait` 不可被 UI 誤顯示成任務結束。
- `succeeded` 只在成功條件滿足時成立，不以「沒有更多文字」作為完成判斷。

## 7. 控制面流程

### 7.1 正常推進

1. 建立 `TaskRun`
2. 控制面判斷為 `queued`
3. worker claim task/node lease
4. execution plane 執行 graph/node
5. node event 更新 `NodeRun.last_progress_at`
6. 若 graph 未完成，控制面根據最新狀態決定下一個 runnable node 或等待條件
7. 所有成功條件滿足後，TaskRun 轉 `succeeded`

### 7.2 Reconcile loop

daemon 每個 tick 至少做以下檢查：

1. 掃描 `queued` 任務，派發可執行工作
2. 掃描 `running` 任務，回收 lease 已過期的 task/node
3. 掃描 `retry_wait` 任務，若 cooldown 到期則轉回 `queued`
4. 掃描 `waiting_external` 任務，若等待條件已滿足則轉回 `queued`
5. 掃描長時間 `no_progress` 任務，進入 repair、replan 或 terminal decision
6. 對 `repairing` / `replanning` 任務檢查是否超出 budget

### 7.3 事件驅動優先

若收到以下事件，控制面應立即嘗試推進，而不等待下次定時掃描：

- `node_status` 變更
- `node.chunk`
- `tool_result`
- `approval_resolved`
- `schedule.fired`
- `job.*`
- `external_webhook_received`

定時掃描是保險，不是主要驅動。

## 8. Failure Classification

任何失敗都必須先分類，不能一律 fallback。

### 8.1 類別

| 類別 | 說明 | 預設處置 |
|---|---|---|
| `transient` | 暫時性外部錯誤，如 timeout、暫時 unavailable | retry with cooldown |
| `deterministic_input` | 輸入或 schema 錯誤，可透過 deterministic normalization 修補 | repair |
| `planner_repairable` | 規劃可修補，但不必整體重畫 | bounded repair |
| `requires_replan` | 現有 graph 已不適用 | replan |
| `waiting_external` | 缺資料、缺批准、等 webhook | waiting_external |
| `deadlock_or_no_progress` | 長時間無前進、重複相同狀態、循環失敗 | terminal 或人工介入 |
| `internal_bug` | 系統自身 bug | fail-fast + diagnostics |

### 8.2 不可接受的 fallback

- 每次失敗都直接重新呼叫 planner
- 每次 reconcile 都呼叫 LLM 問下一步
- 因為沒有文字 chunk 就直接把任務判定結束
- 無上限 retry / repair / replan

## 9. Retry / Repair / Replan 政策

### 9.1 Retry

- 僅限 `transient` 類錯誤
- 必須有 `retry_budget`
- 必須有 `cooldown`
- 每次 retry 要寫入 `AttemptRecord`

### 9.2 Repair

- 優先 deterministic repair
- 僅當 deterministic repair 無法處理且屬高價值節點時，才允許有限次 LLM repair
- 必須有 `repair_budget`
- repair 不可改寫與當前問題無關的圖結構

### 9.3 Replan

- 只在原 graph 已明確無法收斂時使用
- replan 必須保留舊 run 與新 run 的關聯，不可覆蓋歷史
- replan 必須帶版本與原因

## 10. Token 使用政策

### 10.1 預設不耗 token 的控制面行為

- lease claim / renew / expire
- heartbeat
- reconcile 掃描
- cooldown 判斷
- waiting condition 判斷
- failure classification 中的 deterministic 規則
- node/run status 更新

### 10.2 允許耗 token 的情境

- 初始 planner 產生 graph
- bounded repair
- bounded replan
- 明確要求語義判斷且無 deterministic 替代方案的節點

### 10.3 強制護欄

- 每個 TaskRun 需記錄累積 token budget
- 每個 `repair` / `replan` attempt 需記錄 token usage
- 若超出 budget，任務轉 `failed_terminal` 或 `waiting_external`
- 控制面不得在 background tick 中無條件呼叫 LLM

## 11. 多任務平行與公平性

### 11.1 原則

- 以 worker pool / action queue 處理多任務，不綁單一 thread-per-task 模式。
- task lease 與 node lease 需支援多 worker 併行 claim。
- 同一 `TaskRun` 同時最多可允許的活躍節點數，應由 policy 控制。

### 11.2 排程建議

- 支援至少 `FIFO + bounded concurrency`
- 後續可擴充 priority，但本階段不是必要條件
- 單任務不得無限制吃滿所有 worker

## 12. UI 與 API 行為

### 12.1 UI 原則

- UI 只能顯示與操作控制面狀態，不持有執行所有權。
- 任務若為 `running`、`retry_wait`、`waiting_external`、`repairing`，UI 必須視為進行中，而非已結束。
- 即使沒有 `node.chunk`，只要有 `node_status`、`attempt`、`lease`、`waiting reason`，UI 也必須顯示可理解的進度。

### 12.2 最低顯示需求

- 當前任務狀態
- 最近進度時間
- 目前等待原因或 cooldown
- 最近錯誤分類
- 重試/修補剩餘預算

## 13. 與既有模組的接線建議

### 13.1 daemon

- 在 `src/amon/daemon/runner.py` 的既有 tick loop 內加入 control-plane reconcile。
- 保持 `tick_interval_seconds` 可設定，預設可延續現有 5 秒。

### 13.2 jobs runner

- 重用其 heartbeat 精神，但不要直接把 job 狀態當成 task control state。
- 可抽出共用 lease/heartbeat 工具，避免 duplicated logic。

### 13.3 taskgraph runtime

- runtime 仍專注 execution plane。
- runtime 需穩定輸出 `node_status`、`node.chunk`、`run_end` 等事件，供控制面消化。
- runtime 的 terminal 結果不再直接等同整個任務永久終止，需交由控制面做最終判斷。

## 14. 實作階段規劃

### Stage 1：可恢復的最小控制面

- 新增 `TaskRun` / `NodeRun` durable state
- 新增 lease + heartbeat + stale lease recovery
- daemon reconcile 能回收失聯任務並重新排回 `queued`
- UI 顯示 `running/retry_wait/waiting_external`

### Stage 2：有邊界的持續推進

- failure classification
- retry budget / repair budget / cooldown / no-progress timeout
- bounded deterministic repair
- run terminal reason 標準化

### Stage 3：語義修補與重規劃

- bounded LLM repair
- bounded replan
- task lineage / replan chain
- token budget 與 audit

### Stage 4：多 worker 與公平性

- worker pool policy
- per-task concurrency cap
- queue fairness
- 觀測指標與 dashboard

## 15. 驗收條件

### 15.1 功能驗收

- worker 在執行中消失後，任務可在 lease 過期後被重新接續。
- 節點失敗但屬 `transient` 時，不會立即終止整體任務。
- graph 沒有文字輸出但仍有節點狀態時，任務不會被誤判為空回覆而結束。
- 任務若等待外部條件，狀態會停在 `waiting_external`，而不是 `failed` 或靜默消失。
- 任務若掉入無進度循環，系統會在 budget 或 timeout 用盡後顯式終止並留下原因。

### 15.2 非功能驗收

- UI thread 不持有任務執行所有權。
- 控制面 tick 不應無條件呼叫 LLM。
- 多任務平行時，不得因單一 task 卡住所有 worker。
- 對既有 `TaskGraph3Runtime` 與 UI 對外 API 保持向前相容。

## 16. 測試策略

### 16.1 單元測試

- lease claim / renew / expire
- retry budget / repair budget / cooldown 邏輯
- failure classification
- no-progress detector

### 16.2 整合測試

- daemon 重啟後接續未完成任務
- worker 執行中 crash 後重新派工
- graph 無文字輸出但有 node status 的續跑流程
- waiting_external 轉回 queued 的恢復流程

### 16.3 回歸測試

- continuation guard 全過
- 既有 graph 執行 API 不變
- 舊 run 資料缺少新欄位時仍能安全讀取

## 17. 風險與取捨

- 若過早把 repair/replan 全交給 LLM，會造成 token 成本失控與不可預期行為。
- 若完全只靠定時掃描，不靠事件驅動，任務恢復延遲會過高。
- 若完全只靠常駐 thread，不做 durable state，系統重啟或 crash 仍會喪失進度。
- 因此本規格採用混合式：**事件驅動優先，reconcile 補掃保底，durable state 作為唯一真相**。

## 18. 參考依據

截至 2026-03-28，本規格參考下列官方資料與既有 repo 結構：

- Kubernetes controller 是持續把 current state 拉向 desired state 的 control loop：<https://kubernetes.io/docs/reference/command-line-tools-reference/kube-controller-manager>
- Kubernetes watch-based reconciliation 仍保留額外 periodic reconcile 作為保險：<https://kubernetes.io/blog/2025/12/30/kubernetes-v1-35-watch-based-route-reconciliation-in-ccm/>
- Durable orchestration 將 orchestration instance 與 version/state 關聯，支援多個實例並行：<https://learn.microsoft.com/en-us/azure/azure-functions/durable/durable-orchestration-versioning>
- Durable Task Scheduler 將 scheduler 與 app 分離，並結合記憶體與持久化狀態存放：<https://learn.microsoft.com/ja-jp/azure/azure-functions/durable/durable-task-scheduler/durable-task-scheduler>
- OpenAI token 成本以實際模型使用量計，不是背景 thread 自動計費：<https://platform.openai.com/docs/models/gpt-5.1/>

## 19. 本 repo 對應檔案

- `src/amon/daemon/runner.py`
- `src/amon/scheduler/engine.py`
- `src/amon/jobs/runner.py`
- `src/amon/taskgraph3/runtime.py`

