---
name: data-analysis
description: 對 CSV/Parquet/JSON 資料進行分析。當使用者需要進行資料分析、統計計算、趨勢識別或資料視覺化時使用。
---

# 資料分析 (Data Analysis) 工作流程

本技能旨在提供一個標準化的資料分析流程，支援多種資料格式，並能夠生成有洞察力的分析結果和視覺化。

## 何時使用此技能

- 使用者提供了一個 CSV、Parquet 或 JSON 檔案，要求進行分析
- 使用者要求計算統計數據（平均值、中位數、標準差等）
- 使用者要求識別資料中的趨勢或模式
- 使用者要求進行資料清理或預處理
- 使用者要求生成資料視覺化（圖表、圖形）
- 使用者要求進行比較分析或相關性分析

## 工具需求

- `process.exec`: 在安全的 Python 沙箱中執行資料分析程式碼
- 或 `sandbox_run`: 提供更安全的沙箱環境（預設拒絕主機執行）
- 支援的 Python 函式庫: pandas, numpy, matplotlib, seaborn, plotly

## 分析工作流程

### 步驟 1: 理解分析需求

與使用者溝通，明確分析的目標和期望的輸出。

**需求澄清清單:**
- [ ] 分析的主要目標是什麼？
- [ ] 使用者想要什麼樣的輸出格式（統計表格、圖表、文字摘要）？
- [ ] 是否有特定的時間範圍或資料子集需要分析？
- [ ] 是否需要進行資料清理或預處理？
- [ ] 分析的受眾是誰（技術人員、管理層、客戶）？

### 步驟 2: 載入和探索資料

使用 Python 在沙箱環境中載入資料檔案，並進行初步探索。

**探索步驟:**
- [ ] 載入資料檔案（支援 CSV、Parquet、JSON）
- [ ] 檢查資料的形狀（行數和列數）
- [ ] 檢查資料類型和缺失值
- [ ] 顯示前幾行資料以理解結構
- [ ] 生成基本的統計摘要

**Python 程式碼範例:**

```python
import pandas as pd
import numpy as np

# 載入資料
df = pd.read_csv('data.csv')

# 基本探索
print(f"資料形狀: {df.shape}")
print(f"\n資料類型:\n{df.dtypes}")
print(f"\n缺失值:\n{df.isnull().sum()}")
print(f"\n前 5 行:\n{df.head()}")
print(f"\n統計摘要:\n{df.describe()}")
```

### 步驟 3: 資料清理和預處理

根據需要進行資料清理，包括處理缺失值、異常值、資料類型轉換等。

**清理操作:**
- [ ] 處理缺失值（刪除、填充或插值）
- [ ] 識別和處理異常值
- [ ] 轉換資料類型（例如，字串轉日期）
- [ ] 移除重複行
- [ ] 規範化或標準化資料（如需要）
- [ ] 建立新的衍生欄位（如需要）

**Python 程式碼範例:**

```python
# 處理缺失值
df = df.dropna()  # 或 df.fillna(df.mean())

# 移除重複行
df = df.drop_duplicates()

# 轉換資料類型
df['date'] = pd.to_datetime(df['date'])

# 識別異常值（使用 IQR 方法）
Q1 = df['value'].quantile(0.25)
Q3 = df['value'].quantile(0.75)
IQR = Q3 - Q1
outliers = df[(df['value'] < Q1 - 1.5*IQR) | (df['value'] > Q3 + 1.5*IQR)]
```

### 步驟 4: 進行分析

根據使用者的需求進行具體的分析。常見的分析類型包括：

**描述性統計分析:**
- 計算平均值、中位數、標準差、最小值、最大值
- 計算百分位數
- 生成頻率分布表

**分組分析:**
- 按特定欄位分組，計算各組的統計指標
- 比較不同組之間的差異

**趨勢分析:**
- 識別時間序列資料中的趨勢
- 計算增長率或變化率
- 進行季節性分析

**相關性分析:**
- 計算變數之間的相關係數
- 識別強相關的變數對

**Python 程式碼範例:**

```python
# 描述性統計
print(df.describe())
print(f"平均值: {df['value'].mean()}")
print(f"中位數: {df['value'].median()}")
print(f"標準差: {df['value'].std()}")

# 分組分析
grouped = df.groupby('category')['value'].agg(['mean', 'sum', 'count'])
print(grouped)

# 相關性分析
correlation = df[['col1', 'col2', 'col3']].corr()
print(correlation)
```

### 步驟 5: 資料視覺化

根據分析結果生成適當的視覺化圖表，幫助使用者更好地理解資料。

**常見的視覺化類型:**
- 直方圖（Histogram）: 顯示數值分布
- 箱線圖（Box Plot）: 顯示分布和異常值
- 散點圖（Scatter Plot）: 顯示兩個變數之間的關係
- 折線圖（Line Chart）: 顯示時間序列趨勢
- 柱狀圖（Bar Chart）: 比較不同類別的值
- 熱力圖（Heatmap）: 顯示相關性矩陣

**Python 程式碼範例:**

```python
import matplotlib.pyplot as plt
import seaborn as sns

# 直方圖
plt.figure(figsize=(10, 6))
plt.hist(df['value'], bins=30, edgecolor='black')
plt.xlabel('Value')
plt.ylabel('Frequency')
plt.title('Distribution of Values')
plt.savefig('histogram.png', dpi=300, bbox_inches='tight')
plt.close()

# 箱線圖
plt.figure(figsize=(10, 6))
sns.boxplot(data=df, x='category', y='value')
plt.title('Value Distribution by Category')
plt.savefig('boxplot.png', dpi=300, bbox_inches='tight')
plt.close()

# 相關性熱力圖
plt.figure(figsize=(10, 8))
sns.heatmap(df.corr(), annot=True, cmap='coolwarm', center=0)
plt.title('Correlation Matrix')
plt.savefig('correlation_heatmap.png', dpi=300, bbox_inches='tight')
plt.close()
```

### 步驟 6: 生成分析報告

將分析結果、關鍵發現和建議整理成一份清晰的報告。

**報告結構:**

```markdown
# 資料分析報告

## 執行摘要
簡要說明分析的目標、主要發現和建議。

## 資料概況
- 資料來源和時間範圍
- 資料規模（行數、列數）
- 資料品質（缺失值、異常值）

## 分析方法
描述使用的分析方法和技術。

## 主要發現
列出分析中發現的重要洞察，包括：
- 統計指標
- 趨勢和模式
- 異常值或特殊情況

## 視覺化
包含相關的圖表和圖形。

## 建議和後續步驟
基於分析結果提出的建議和可能的後續行動。

## 附錄
詳細的統計表格和計算過程。
```

## 最佳實踐

1. **資料驗證**: 始終驗證資料的品質和完整性，在進行分析前進行清理。

2. **清晰的視覺化**: 選擇適當的圖表類型，確保視覺化清晰易懂，避免過度裝飾。

3. **統計嚴謹性**: 使用適當的統計方法，並報告置信區間或 p 值等統計指標。

4. **避免過度解釋**: 不要從相關性推斷因果關係，除非有強有力的證據。

5. **考慮背景**: 將分析結果放在業務背景中解釋，提供可行的洞察。

6. **可重現性**: 記錄所有的分析步驟和參數，確保分析可以被重現。

7. **清晰的溝通**: 使用簡單的語言解釋分析結果，避免過度技術化的術語。

## 常見的分析陷阱

- **忽視資料品質**: 不清理資料就進行分析，導致結果不準確
- **選擇偏差**: 只分析支持特定結論的資料子集
- **過度擬合**: 建立過於複雜的模型，導致泛化能力差
- **忽視異常值**: 不檢查和處理異常值，導致結果扭曲
- **混淆相關性和因果性**: 假設相關的變數之間存在因果關係
- **不適當的視覺化**: 選擇不適合資料類型的圖表
