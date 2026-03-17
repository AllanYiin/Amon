# Mermaid 中文問題排錯指引

## 問題 1：Parse error / 語法錯誤

**症狀：** 圖表完全不顯示，控制台出現 Parse error

**最常見原因：** 節點標籤含有特殊字元未加引號

```
# 觸發錯誤的字元：( ) [ ] { } : , # " '
```

**解法：** 用雙引號包裹整個節點標籤
```
# 有問題
flowchart LR
    A[系統(System)] --> B[資料庫:主機]

# 修正後
flowchart LR
    A["系統(System)"] --> B["資料庫:主機"]
```

---

## 問題 2：erDiagram 欄位名含中文報錯

**症狀：** ER 圖 attribute 名稱含中文時報 Parse error

**解法：** 欄位名改英文，使用 comment 加中文說明

```
# 有問題
erDiagram
    用戶 {
        int 用戶編號 PK
        string 姓名
    }

# 修正後
erDiagram
    用戶 {
        int id PK "用戶編號"
        string name "姓名"
    }
```

---

## 問題 3：classDiagram 方法名含中文報錯

**症狀：** class 的方法定義含中文時，某些版本解析失敗

**解法：** 方法名改英文

```
# 可能有問題
classDiagram
    class 商品管理器 {
        +新增商品(name, price)
        +刪除商品(id)
    }

# 穩健寫法
classDiagram
    class 商品管理器 {
        +addProduct(name, price)
        +deleteProduct(id)
    }
```

---

## 問題 4：gitgraph branch 名含中文報錯

**症狀：** `branch 中文名稱` 這行報語法錯誤

**解法：** branch 名改英文，commit 訊息可保留中文

```
# 有問題
gitgraph
    branch 新功能分支

# 修正後
gitgraph
    branch feature/new-feature
    commit id: "新功能開發完成"
```

---

## 問題 5：sequenceDiagram 中文 participant 含空格

**症狀：** participant 名稱含空格時渲染失敗

**解法：** 使用 `as` 別名語法

```
# 有問題
sequenceDiagram
    participant 前端 系統
    participant 後端 API

# 修正後
sequenceDiagram
    participant FE as 前端系統
    participant BE as 後端API
```

---

## 問題 6：中文字顯示為方塊（缺字型）

**症狀：** 圖表渲染成功，但中文顯示為 □ 方塊

**原因：** 渲染環境缺乏中文字型

**解法：** 在 mermaid.initialize 設定字型

```javascript
mermaid.initialize({
  startOnLoad: true,
  theme: 'default',
  themeVariables: {
    fontFamily: '"Noto Sans TC", "Microsoft JhengHei", "PingFang TC", "STHeiti", sans-serif'
  }
});
```

或在 HTML `<head>` 引入 Google Fonts：
```html
<link href="https://fonts.googleapis.com/css2?family=Noto+Sans+TC&display=swap" rel="stylesheet">
```

---

## 問題 7：Gantt 日期格式錯誤

**症狀：** 甘特圖 task 不顯示或位置錯誤

**解法：** 確保 dateFormat 與 task 日期格式一致

```
gantt
    dateFormat YYYY-MM-DD    ← 格式聲明
    section 工作
    任務一 :2024-01-01, 7d   ← 日期必須符合 YYYY-MM-DD 格式
```

---

## 快速診斷清單

- [ ] 節點標籤含特殊符號 → 加雙引號
- [ ] erDiagram 欄位名 → 改英文
- [ ] classDiagram 方法名 → 改英文
- [ ] gitgraph branch 名 → 改英文
- [ ] participant 含空格 → 用 as 別名
- [ ] 中文方塊 → 設定中文字型
- [ ] Gantt 日期 → 確認格式一致
