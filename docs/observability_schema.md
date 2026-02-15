# Observability Schema（Phase C 小步）

本文定義 Amon 現階段可觀測性最小 schema，先覆蓋 UI server 的 `/health` 與 `/metrics`。

## 1. `/health` JSON schema（v0.1）

`GET /health`

```json
{
  "status": "ok",
  "service": "amon-ui-server",
  "queue_depth": 0,
  "recent_error_rate": {
    "window_seconds": 300,
    "request_count": 12,
    "error_count": 1,
    "error_rate": 0.0833,
    "uptime_seconds": 42
  },
  "observability": {
    "schema_version": "v0.1",
    "metrics_window_seconds": 300,
    "links": {
      "metrics": "/metrics"
    }
  }
}
```

### 欄位關聯

- `recent_error_rate.window_seconds` 與 `observability.metrics_window_seconds` 應一致（同一個 rolling window）。
- `queue_depth` 與 `/metrics` 的 `amon_ui_queue_depth` 對應。
- `recent_error_rate.request_count` / `error_count` / `error_rate` 分別對應 `/metrics` 的：
  - `amon_ui_request_total`
  - `amon_ui_error_total`
  - `amon_ui_error_rate`

## 2. `/metrics` 指標（Prometheus text format）

`GET /metrics`

目前最小集合：

- `amon_ui_queue_depth`（gauge）
- `amon_ui_request_total`（rolling window gauge）
- `amon_ui_error_total`（rolling window gauge）
- `amon_ui_error_rate`（rolling window gauge）

## 3. 相容性策略

- `schema_version` 採明示版本，未來新增欄位以「向後相容」為原則。
- 現有欄位不移除；若需汰換欄位，先新增替代欄位並標記 deprecated。
