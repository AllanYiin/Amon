# Test Plan: slide-content-planner

本測試計畫同時覆蓋「觸發準確度」與「交付物品質」。

## 1) Triggering tests

目標：該載入時載入，不該載入時不載入。

### Should trigger（建議 10–20）

- 幫我規劃一份關於「供應鏈韌性」的簡報內容，受眾是企業決策者
- 投影片內容規劃：主題 AI 治理；受眾董事會；要改變他們對風險的看法
- 我要做一份 12 頁 pitch deck 的內容規劃（含封面與 Q&A）
- 請用第一性原理幫我拆解主題並設計投影片大綱
- /run\n主題：新產品上市策略\n受眾：通路夥伴\n目標：願意加入聯盟
- /autorun\n主題：2026 年行銷策略\n受眾：管理層\n頁數：10

### Should NOT trigger（建議 10–20）

- 把這份 PPTX 的字體改成 18pt（屬於編輯既有簡報）
- 幫我把 SVG 轉成 PNG（屬於轉檔/繪圖工作，非內容規劃）
- 介紹一下瑞士國際字體風格（純知識解釋）
- 做一張海報（偏平面設計，不是投影片內容規劃）
- 幫我找附近餐廳（與簡報無關）

## 2) Functional tests

目標：端到端輸出結構正確，且可落地。

### Test case A：B2B SaaS 產品 pitch（未指定頁數）
- Given:
  - 主題：B2B SaaS 新品 Pitch
  - 受眾：企業 IT/業務決策者
  - 目標：安排 PoC 會議
  - 未提供頁數/色調/比例
- When: 產出內容規劃
- Then:
  - 有【信息抽取】（未提供欄位以預設或假設標註）
  - 自動配置合理頁數（含封面與 Q&A、無目錄頁）
  - 逐頁皆有：title/takeaway/supporting points/evidence needed/speaker note
  - 視覺元素表逐頁完成，且無「只有文字」頁

### Test case B：/run 逐步確認
- Given: 使用者輸入以 /run 開頭且只提供主題
- When: 執行 Step 0
- Then:
  - 只輸出【信息抽取】並請使用者確認，不提前輸出後續內容

### Test case C：含數據/新聞需求
- Given:
  - 主題：電動車市場趨勢
  - 受眾：投資委員會
  - 目標：核准投資案
- When: 產出內容規劃
- Then:
  - 涉及數據/新聞的頁面，規劃中必含「來源/查證需求」（例如：IEA/官方統計/主要媒體）

## 3) Performance comparison

### Baseline（無 skill）
- 常見問題：只給大綱、沒有逐頁欄位、缺視覺化規劃、缺封面/Q&A、頁數不合理。

### With skill
- 應改善：固定結構輸出、逐頁可落地、視覺化覆蓋率 100%、有 QA 清單。

## 4) Release readiness checklist

- [ ] `format_check.py` 0 errors
- [ ] `quick_validate.py` passes
- [ ] 3 類功能測試至少各跑 1 次
- [ ] 過度觸發（over-trigger）風險已用 Should NOT trigger 測試覆蓋
- [ ] 版本號已更新（頂層 version: 西元年.月.日）
