---
name: spreadsheet-workflows
description: 報表 xlsx（整理、公式、檢核）。當使用者需要建立、編輯或分析 Excel 試算表時使用。
---

# 試算表工作流程 (Spreadsheet Workflows) 工作流程

本技能旨在提供一個標準化的方法來建立、編輯和分析 Excel 試算表，包括資料整理、公式設定和資料驗證。

## 何時使用此技能

- 使用者要求建立一個 Excel 報表（「請為我建立一個銷售報表」）
- 使用者要求整理和格式化試算表資料
- 使用者要求添加公式和計算
- 使用者要求進行資料驗證和檢核
- 使用者要求建立圖表和視覺化
- 使用者要求進行資料分析和摘要
- 使用者要求導出或轉換試算表

## 工具需求

- `artifacts.write_file`: 將試算表檔案寫入檔案系統
- openpyxl: Python 中的 Excel 檔案處理
- pandas: 資料處理和分析
- 支援 XLSX 格式

## 試算表工作流程

### 步驟 1: 明確試算表需求

與使用者溝通，確定試算表的具體需求和結構。

**需求澄清清單:**
- [ ] 試算表的主要目的是什麼？
- [ ] 需要包含哪些資料和欄位？
- [ ] 資料來源是什麼？
- [ ] 是否需要進行資料計算或彙總？
- [ ] 是否需要圖表或視覺化？
- [ ] 是否需要資料驗證或檢核？
- [ ] 預期的使用者是誰？
- [ ] 是否有特定的格式或範本要求？

### 步驟 2: 設計試算表結構

設計試算表的邏輯結構和組織方式。

**結構設計清單:**
- [ ] 定義工作表的數量和名稱
- [ ] 確定每個工作表的目的
- [ ] 規劃欄位和資料類型
- [ ] 設計資料流程和依賴關係
- [ ] 識別需要的計算和彙總
- [ ] 規劃格式和樣式

**試算表結構範例:**

```
工作簿: 銷售報表

工作表 1: 原始資料
- 日期 | 產品 | 數量 | 單價 | 總額 | 地區

工作表 2: 月度彙總
- 月份 | 總銷售額 | 平均單價 | 交易數量

工作表 3: 地區分析
- 地區 | 銷售額 | 市場份額 | 成長率

工作表 4: 圖表
- 銷售趨勢圖
- 地區分布圖
```

### 步驟 3: 準備和導入資料

準備資料並將其導入試算表。

**資料準備清單:**
- [ ] 清理和驗證源資料
- [ ] 標準化資料格式（日期、數字、文字）
- [ ] 移除重複和不相關的資料
- [ ] 處理缺失值
- [ ] 建立資料字典（欄位說明）

**資料導入範例:**

```python
import pandas as pd
from openpyxl import Workbook
from openpyxl.utils.dataframe import dataframe_to_rows

# 讀取源資料
df = pd.read_csv('sales_data.csv')

# 清理資料
df = df.drop_duplicates()
df['date'] = pd.to_datetime(df['date'])
df['amount'] = pd.to_numeric(df['amount'])

# 建立 Excel 工作簿
wb = Workbook()
ws = wb.active
ws.title = '原始資料'

# 寫入資料
for r_idx, row in enumerate(dataframe_to_rows(df, index=False, header=True), 1):
    for c_idx, value in enumerate(row, 1):
        ws.cell(row=r_idx, column=c_idx, value=value)

wb.save('sales_report.xlsx')
```

### 步驟 4: 應用格式和樣式

應用適當的格式和樣式，使試算表易於閱讀和理解。

**格式化清單:**
- [ ] 設定列寬和行高
- [ ] 應用標題樣式
- [ ] 設定資料格式（日期、貨幣、百分比）
- [ ] 應用條件格式（例如，顏色編碼）
- [ ] 凍結窗格（如需要）
- [ ] 應用邊框和背景顏色
- [ ] 設定字體和字號

**格式化範例:**

```python
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

# 應用標題格式
header_fill = PatternFill(start_color='4472C4', end_color='4472C4', fill_type='solid')
header_font = Font(bold=True, color='FFFFFF')

for cell in ws[1]:
    cell.fill = header_fill
    cell.font = header_font
    cell.alignment = Alignment(horizontal='center', vertical='center')

# 應用資料格式
for row in ws.iter_rows(min_row=2, max_row=ws.max_row, min_col=1, max_col=ws.max_column):
    for cell in row:
        if cell.column == 4:  # 假設第 4 列是金額
            cell.number_format = '$#,##0.00'
        elif cell.column == 1:  # 假設第 1 列是日期
            cell.number_format = 'yyyy-mm-dd'

# 設定列寬
ws.column_dimensions['A'].width = 12
ws.column_dimensions['B'].width = 20
```

### 步驟 5: 添加公式和計算

添加公式進行計算和資料彙總。

**常見的公式類型:**

| 公式 | 用途 | 範例 |
|------|------|------|
| SUM | 求和 | `=SUM(A1:A10)` |
| AVERAGE | 平均值 | `=AVERAGE(B1:B10)` |
| COUNT | 計數 | `=COUNT(C1:C10)` |
| IF | 條件判斷 | `=IF(A1>100, "高", "低")` |
| VLOOKUP | 垂直查詢 | `=VLOOKUP(A1, 表, 2, FALSE)` |
| SUMIF | 條件求和 | `=SUMIF(A1:A10, "東區", B1:B10)` |
| INDEX/MATCH | 高級查詢 | `=INDEX(B:B, MATCH(A1, A:A, 0))` |

**公式添加範例:**

```python
from openpyxl.utils import get_column_letter

# 添加小計行
ws['A11'] = '合計'
ws['D11'] = f'=SUM(D2:D10)'
ws['D11'].font = Font(bold=True)

# 添加計算欄位（例如，總額 = 數量 × 單價）
for row in range(2, ws.max_row + 1):
    ws[f'E{row}'] = f'=B{row}*C{row}'

# 添加百分比欄位（例如，市場份額）
total_sales = f'=SUM(D2:D{ws.max_row})'
for row in range(2, ws.max_row + 1):
    ws[f'F{row}'] = f'=D{row}/{total_sales}'
    ws[f'F{row}'].number_format = '0.0%'
```

### 步驟 6: 建立樞紐分析表和摘要

建立樞紐分析表或摘要表，進行資料彙總和分析。

**摘要表範例:**

```python
# 使用 pandas 建立摘要
summary = df.groupby('地區').agg({
    '數量': 'sum',
    '總額': 'sum',
    '產品': 'count'
}).rename(columns={'產品': '交易數'})

# 計算百分比
summary['市場份額'] = (summary['總額'] / summary['總額'].sum() * 100).round(2)

# 寫入摘要工作表
summary_ws = wb.create_sheet('地區摘要')
for r_idx, row in enumerate(dataframe_to_rows(summary.reset_index(), index=False, header=True), 1):
    for c_idx, value in enumerate(row, 1):
        summary_ws.cell(row=r_idx, column=c_idx, value=value)
```

### 步驟 7: 添加資料驗證和檢核

添加資料驗證規則，確保資料品質。

**驗證規則清單:**
- [ ] 必填欄位檢查
- [ ] 資料類型驗證
- [ ] 數值範圍驗證
- [ ] 下拉列表（用於限制選項）
- [ ] 自訂驗證規則
- [ ] 錯誤訊息和警告

**驗證範例:**

```python
from openpyxl.worksheet.datavalidation import DataValidation

# 建立下拉列表驗證
dv = DataValidation(type='list', formula1='"東區,西區,南區,北區"', allow_blank=False)
dv.error = '請選擇有效的地區'
dv.errorTitle = '無效輸入'
ws.add_data_validation(dv)
dv.add(f'B2:B{ws.max_row}')

# 建立數值範圍驗證
dv_number = DataValidation(type='whole', operator='greaterThan', formula1='0')
dv_number.error = '數量必須大於 0'
ws.add_data_validation(dv_number)
dv_number.add(f'C2:C{ws.max_row}')
```

### 步驟 8: 建立圖表和視覺化

建立圖表和視覺化，幫助理解資料。

**常見的圖表類型:**
- 柱狀圖：比較不同類別的值
- 折線圖：顯示時間序列趨勢
- 圓餅圖：顯示部分與整體的關係
- 散點圖：顯示兩個變數之間的關係
- 熱力圖：顯示資料密度或強度

**圖表建立範例:**

```python
from openpyxl.chart import BarChart, Reference, LineChart

# 建立柱狀圖
chart = BarChart()
chart.type = 'col'
chart.title = '地區銷售額'
chart.x_axis.title = '地區'
chart.y_axis.title = '銷售額'

# 添加資料
data = Reference(ws, min_col=2, min_row=1, max_row=ws.max_row)
cats = Reference(ws, min_col=1, min_row=2, max_row=ws.max_row)
chart.add_data(data, titles_from_data=True)
chart.set_categories(cats)

# 添加圖表到工作表
ws.add_chart(chart, 'H2')
```

### 步驟 9: 審查和驗證

仔細審查試算表，確保準確性和完整性。

**審查清單:**
- [ ] 驗證所有資料的準確性
- [ ] 檢查公式的正確性
- [ ] 驗證計算結果
- [ ] 檢查格式的一致性
- [ ] 驗證資料驗證規則
- [ ] 測試所有交互功能
- [ ] 檢查列印版本的外觀
- [ ] 獲取使用者反饋

### 步驟 10: 導出和交付

將試算表導出並準備交付。

**導出清單:**
- [ ] 保存為 XLSX 格式
- [ ] 建立備份副本
- [ ] 測試在不同 Excel 版本中的相容性
- [ ] 準備使用說明（如需要）
- [ ] 記錄版本和修改歷史

## 最佳實踐

1. **清晰的結構**: 使用邏輯的組織和清晰的標題。

2. **資料完整性**: 驗證所有資料的準確性和完整性。

3. **公式文件化**: 添加註解說明複雜的公式。

4. **版本控制**: 保存不同版本的試算表，追蹤變更。

5. **效能優化**: 避免過於複雜的公式和大量的計算。

6. **安全性**: 保護敏感資料，使用密碼保護（如需要）。

7. **易用性**: 設計使用者友好的介面，提供清晰的說明。

## 常見的試算表問題

- **公式錯誤**: 公式中的參考錯誤或邏輯錯誤
- **資料不一致**: 不同工作表中的資料不同步
- **效能問題**: 試算表過大或公式過於複雜
- **格式混亂**: 格式不一致或難以閱讀
- **資料驗證不足**: 缺乏資料驗證導致錯誤輸入
- **文件化不足**: 缺乏說明和文件
- **版本混亂**: 多個版本的試算表導致混淆
