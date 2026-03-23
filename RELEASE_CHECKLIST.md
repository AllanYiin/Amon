# Release Checklist

## 發版前最少檢查

```bash
python -m compileall src tests
python -m unittest \
  tests.test_thread_continuation_guard \
  tests.test_thread_continuation_flow \
  tests.test_ui_thread_stream_init \
  tests.test_thread_store
python -m unittest tests.smoke.test_vnext_ui_smoke
python -m unittest tests.smoke.test_vnext_examples_smoke
```

## vNext 專項

- manifest fixture 可被 round-trip 與 validate refs
- compiled graph fixture 可通過 v3 validator
- run stream 可用 `Last-Event-ID` 續接
- preview fallback 不假裝成功
- trigger 只能產生標準 run request
- workspace UI / CLI / API smoke tests 通過

## 人工驗收

1. 確認 README、SPEC 與 docs 連結沒有斷
2. 確認 examples JSON 可解析
3. 確認 `amon ui --port 8000` 的實際啟動方式
4. 確認已知限制已更新到 [docs/known_limits.md](D:/PycharmProjects/Amon/docs/known_limits.md)

詳細 smoke 項目可參考舊版 [docs/release-checklist.md](D:/PycharmProjects/Amon/docs/release-checklist.md)。
