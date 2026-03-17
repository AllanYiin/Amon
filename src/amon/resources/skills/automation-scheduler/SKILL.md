---
name: automation-scheduler
description: 建立定期任務（每日晨報、每週回顧）。當使用者需要設定自動化的、定期執行的任務時使用。
---

# 自動化排程 (Automation Scheduler) 工作流程

本技能旨在提供一個標準化的方法來建立和管理定期自動化任務，包括每日、每週、每月等各種時間間隔的任務。

## 何時使用此技能

- 使用者要求建立每日晨報（「每天早上 8 點發送晨報」）
- 使用者要求建立每週回顧（「每週一生成週報」）
- 使用者要求建立定期資料備份任務
- 使用者要求建立定期監控或檢查任務
- 使用者要求建立定期清理或維護任務
- 使用者要求修改或取消現有的排程任務

## 工具需求

- Cron 表達式支援（用於時間排程）
- 任務排程引擎（如 APScheduler、Celery 等）
- 任務執行環境（可以是本地或遠程）

## 排程工作流程

### 步驟 1: 明確任務需求

與使用者溝通，確定要自動化的任務的具體需求。

**需求澄清清單:**
- [ ] 任務的具體內容是什麼？
- [ ] 任務應該多頻繁執行（每天、每週、每月、自定義）？
- [ ] 任務應該在什麼時間執行？
- [ ] 是否有時區考慮？
- [ ] 任務失敗時應該如何處理（重試、通知、忽略）？
- [ ] 任務的執行結果應該如何報告？
- [ ] 任務是否有依賴項或前置條件？

### 步驟 2: 設計任務的執行邏輯

定義任務應該執行的具體步驟和邏輯。

**任務設計清單:**
- [ ] 任務的輸入和輸出是什麼？
- [ ] 任務涉及哪些系統或資源？
- [ ] 是否需要資料庫存取、API 呼叫或檔案操作？
- [ ] 任務的預期執行時間是多少？
- [ ] 任務是否有副作用或依賴項？
- [ ] 是否需要錯誤處理和日誌記錄？

**任務執行邏輯範例:**

```python
def daily_morning_report():
    """
    每日晨報任務
    """
    try:
        # 1. 收集資料
        data = collect_daily_data()
        
        # 2. 生成報告
        report = generate_report(data)
        
        # 3. 發送報告
        send_email(report)
        
        # 4. 記錄日誌
        log_task_execution("success", "晨報已發送")
        
    except Exception as e:
        log_task_execution("error", str(e))
        notify_admin(f"晨報任務失敗: {e}")
```

### 步驟 3: 定義排程時間

使用 Cron 表達式或其他排程格式定義任務的執行時間。

**Cron 表達式格式:**

Cron 表達式由 6 個欄位組成，表示秒、分鐘、小時、日期、月份和星期幾。

```
秒 分 時 日 月 週
0  0  8  *  *  *    # 每天早上 8:00:00
0  0  8  *  *  1-5  # 週一到週五早上 8:00:00
0  0  9,17 * * *    # 每天早上 9:00 和下午 5:00
0  0  0  1  *  *    # 每月 1 日午夜
0  0  0  *  *  0    # 每週日午夜
*/15 * * * * *      # 每 15 分鐘
```

**Cron 欄位說明:**

| 欄位 | 範圍 | 特殊字符 | 說明 |
|------|------|---------|------|
| 秒 | 0-59 | , - * / | 任務執行的秒數 |
| 分 | 0-59 | , - * / | 任務執行的分鐘 |
| 時 | 0-23 | , - * / | 任務執行的小時（24 小時制） |
| 日 | 1-31 | , - * / | 任務執行的日期 |
| 月 | 1-12 | , - * / | 任務執行的月份 |
| 週 | 0-6 | , - * / | 任務執行的星期（0=星期日） |

**常見的排程範例:**

| 需求 | Cron 表達式 |
|------|-----------|
| 每天早上 8 點 | `0 0 8 * * *` |
| 每週一早上 9 點 | `0 0 9 * * 1` |
| 每月 1 日午夜 | `0 0 0 1 * *` |
| 每 30 分鐘 | `0 */30 * * * *` |
| 工作日每小時 | `0 0 * * * 1-5` |
| 每 5 分鐘 | `0 */5 * * * *` |

### 步驟 4: 配置排程參數

設定排程任務的各種參數，包括重試策略、超時設定等。

**排程配置清單:**
- [ ] 任務名稱和描述
- [ ] Cron 表達式或時間間隔
- [ ] 時區設定
- [ ] 最大重試次數
- [ ] 重試延遲
- [ ] 任務超時時間
- [ ] 失敗通知方式
- [ ] 成功日誌記錄

**配置範例:**

```python
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

scheduler = BackgroundScheduler()

# 新增每日晨報任務
scheduler.add_job(
    func=daily_morning_report,
    trigger=CronTrigger(hour=8, minute=0, second=0),
    id='daily_morning_report',
    name='每日晨報',
    max_instances=1,  # 防止並發執行
    misfire_grace_time=300,  # 如果錯過，在 5 分鐘內仍然執行
    coalesce=True,  # 如果多個執行被跳過，只執行一次
    replace_existing=True
)

scheduler.start()
```

### 步驟 5: 實施錯誤處理和監控

為排程任務實施適當的錯誤處理和監控機制。

**錯誤處理策略:**
- [ ] 捕捉和記錄所有例外
- [ ] 實施重試邏輯
- [ ] 通知管理員失敗情況
- [ ] 記錄詳細的錯誤堆棧
- [ ] 實施降級策略（如適用）

**監控清單:**
- [ ] 任務執行時間
- [ ] 任務成功/失敗率
- [ ] 任務執行日誌
- [ ] 系統資源使用情況
- [ ] 任務隊列長度

**錯誤處理範例:**

```python
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

def execute_scheduled_task(task_func, task_name, max_retries=3):
    """
    執行排程任務，包含重試邏輯
    """
    for attempt in range(max_retries):
        try:
            logger.info(f"開始執行任務: {task_name} (嘗試 {attempt + 1}/{max_retries})")
            task_func()
            logger.info(f"任務成功完成: {task_name}")
            return True
            
        except Exception as e:
            logger.error(f"任務執行失敗: {task_name}, 錯誤: {str(e)}")
            if attempt < max_retries - 1:
                logger.info(f"將在 60 秒後重試...")
                time.sleep(60)
            else:
                notify_admin(f"任務 {task_name} 在 {max_retries} 次嘗試後仍然失敗")
                return False
```

### 步驟 6: 測試排程任務

在部署到生產環境前，充分測試排程任務。

**測試清單:**
- [ ] 手動執行任務，驗證邏輯正確
- [ ] 驗證 Cron 表達式的正確性
- [ ] 測試錯誤處理和重試機制
- [ ] 驗證通知和日誌記錄
- [ ] 測試邊界情況（例如，月末、年末）
- [ ] 驗證時區處理

**測試程式碼範例:**

```python
from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime, timedelta

# 建立測試排程器
scheduler = BackgroundScheduler()

# 新增一個立即執行的測試任務
scheduler.add_job(
    func=daily_morning_report,
    trigger='date',
    run_date=datetime.now() + timedelta(seconds=5),
    id='test_task'
)

scheduler.start()

# 等待任務執行
time.sleep(10)

# 驗證任務是否執行成功
job = scheduler.get_job('test_task')
if job:
    print("任務仍在隊列中，可能未執行")
else:
    print("任務已執行並移除")
```

### 步驟 7: 部署和監控

將排程任務部署到生產環境，並進行持續監控。

**部署清單:**
- [ ] 配置生產環境的排程器
- [ ] 驗證任務在生產環境中正確執行
- [ ] 設定監控和警報
- [ ] 記錄所有任務執行
- [ ] 建立備份和恢復計劃

**監控儀表板應包含:**
- 任務執行歷史
- 成功/失敗率
- 平均執行時間
- 最後執行時間和下次執行時間
- 任務日誌和錯誤訊息

## 最佳實踐

1. **使用 UTC 時區**: 在伺服器上使用 UTC 時區，避免時區轉換的複雜性。

2. **冪等性設計**: 設計任務使其可以安全地重複執行而不產生不良副作用。

3. **詳細日誌記錄**: 記錄任務的開始、結束和任何重要的中間步驟。

4. **監控和警報**: 設定監控系統，及時發現和報告任務失敗。

5. **定期審查**: 定期審查排程任務的執行情況，優化配置。

6. **文件化**: 清晰地文件化每個排程任務的目的、時間表和依賴項。

7. **版本控制**: 將排程配置保存在版本控制系統中，便於追蹤變更。

## 常見的排程陷阱

- **時區混亂**: 不同系統使用不同時區導致執行時間不符
- **並發執行**: 同一任務被多次並發執行，導致資料不一致
- **錯過執行**: 排程器停止或重啟導致某些執行被跳過
- **資源洩漏**: 任務未正確清理資源，導致累積問題
- **依賴項失敗**: 外部依賴項失敗導致整個任務失敗
- **監控不足**: 無法及時發現和解決問題
