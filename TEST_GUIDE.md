# TEST_GUIDE

本專案測試規範如下：

## 唯一測試入口
請使用以下命令執行測試：

```bash
python -m unittest
```

- 不應另行定義其他主要測試入口作為正式流程。
- 若需要指定子集合，仍應以 `python -m unittest` 的標準機制延伸。

## 網路依賴限制
- 所有測試必須可在離線（無外網）環境執行。
- 測試不得依賴外部第三方服務、公開 API 或即時網路資源。
- 若流程需要外部互動，應改以 stub/mock/fixture 處理，確保可重現與穩定。

## 建議執行順序
1. 先執行最小品質檢查：
   ```bash
   python -m compileall src tests
   ```
2. 再執行測試入口：
   ```bash
   python -m unittest
   ```
