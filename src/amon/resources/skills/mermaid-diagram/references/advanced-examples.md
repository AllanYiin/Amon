# Mermaid 進階圖表範例

## 子圖（Subgraph）

```mermaid
flowchart TD
    subgraph 前端層["前端層 (Frontend)"]
        A[React 應用]
        B[狀態管理]
    end
    subgraph 後端層["後端層 (Backend)"]
        C[API Gateway]
        D[業務邏輯]
        E[(PostgreSQL)]
    end
    subgraph 外部服務["外部服務"]
        F[金流 API]
        G[簡訊服務]
    end

    A --> C
    B --> A
    C --> D
    D --> E
    D --> F
    D --> G
```

## 系統架構圖（Architecture）

```mermaid
flowchart LR
    subgraph 用戶端
        App["手機 App"]
        Web["網頁瀏覽器"]
    end
    subgraph CDN
        CF["CloudFront"]
    end
    subgraph 應用層
        LB["負載均衡器"]
        S1["服務節點 1"]
        S2["服務節點 2"]
    end
    subgraph 資料層
        Cache["Redis 快取"]
        DB[("主資料庫")]
        Read[("讀取副本")]
    end

    App & Web --> CF
    CF --> LB
    LB --> S1 & S2
    S1 & S2 --> Cache
    S1 & S2 --> DB
    S1 & S2 --> Read
```

## 複雜序列圖（含 loop 和 alt）

```mermaid
sequenceDiagram
    actor 用戶
    participant 前端
    participant 認證服務
    participant 商品服務

    用戶->>前端: 加入購物車
    前端->>認證服務: 驗證 JWT Token

    alt Token 有效
        認證服務-->>前端: 認證成功
        前端->>商品服務: 檢查庫存

        loop 每件商品
            商品服務->>商品服務: 鎖定庫存
        end

        商品服務-->>前端: 庫存確認
        前端-->>用戶: 加入購物車成功
    else Token 過期
        認證服務-->>前端: 401 Unauthorized
        前端-->>用戶: 請重新登入
    end
```

## 複雜狀態圖（含並行狀態）

```mermaid
stateDiagram-v2
    [*] --> 初始化

    state 初始化 {
        [*] --> 載入設定
        載入設定 --> 連接資料庫
        連接資料庫 --> [*]
    }

    初始化 --> 運行中

    state 運行中 {
        [*] --> 等待請求
        等待請求 --> 處理請求 : 收到請求
        處理請求 --> 等待請求 : 處理完成
    }

    運行中 --> 錯誤 : 發生異常
    運行中 --> 關閉中 : 收到停止信號
    錯誤 --> 運行中 : 重試成功
    錯誤 --> 關閉中 : 無法恢復
    關閉中 --> [*]
```

## Gitgraph（Git 流程）

```mermaid
gitgraph
    commit id: "初始化專案"
    commit id: "加入基礎架構"

    branch develop
    checkout develop
    commit id: "開發環境設定"

    branch feature/user-auth
    checkout feature/user-auth
    commit id: "新增登入功能"
    commit id: "新增 JWT 驗證"
    commit id: "撰寫單元測試"

    checkout develop
    merge feature/user-auth id: "合併用戶認證"

    branch feature/payment
    checkout feature/payment
    commit id: "整合金流 API"

    checkout develop
    merge feature/payment id: "合併金流功能"

    checkout main
    merge develop id: "v1.0.0 正式發布" tag: "v1.0.0"
```

## 複合型 Gantt

```mermaid
gantt
    title 2024 年 SaaS 產品路線圖
    dateFormat YYYY-MM-DD
    excludes weekends, 2024-01-01, 2024-02-10

    section 第一季 MVP
    用戶認證模組   :done,     a1, 2024-01-02, 2024-01-12
    產品目錄       :done,     a2, after a1, 10d
    購物車功能     :active,   a3, after a2, 7d
    金流整合       :crit,     a4, after a3, 14d

    section 第二季 優化
    效能優化       :          b1, 2024-04-01, 21d
    行動版優化     :          b2, after b1, 14d
    A/B 測試框架   :          b3, 2024-04-15, 21d

    section 里程碑
    Alpha 測試     :milestone, m1, 2024-01-31, 0d
    Beta 上線      :milestone, m2, 2024-03-29, 0d
    正式上線       :milestone, m3, 2024-06-28, 0d
```

## XY Chart（數據圖）

```mermaid
xychart-beta
    title "月度銷售數據（萬元）"
    x-axis [一月, 二月, 三月, 四月, 五月, 六月]
    y-axis "銷售額" 0 --> 500
    bar [120, 180, 150, 250, 300, 420]
    line [120, 180, 150, 250, 300, 420]
```

## Sankey（桑基圖）

```mermaid
sankey-beta
    用戶來源, 自然搜尋, 1200
    用戶來源, 社群媒體, 800
    用戶來源, 直接流量, 600
    自然搜尋, 購買, 300
    自然搜尋, 離開, 900
    社群媒體, 購買, 200
    社群媒體, 離開, 600
    直接流量, 購買, 250
    直接流量, 離開, 350
```
