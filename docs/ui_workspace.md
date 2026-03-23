# UI Workspace

## 目的

vNext workspace 是單一入口 UI 中的新工作台視圖，不另開第二套前端應用。

入口：

- [src/amon/ui/index.html](D:/PycharmProjects/Amon/src/amon/ui/index.html)
- [src/amon/ui/static/js/views/workspace.js](D:/PycharmProjects/Amon/src/amon/ui/static/js/views/workspace.js)

注意：`amon ui --port 8000` 目前在 CLI 路徑下可能立即返回 `exit code 0`，因此這份文件描述的是 workspace 視圖與 API/UI 契約，不代表前景啟動問題已解。

## 畫面區塊

1. Project summary
2. Definition list
3. Run controls
4. Streaming output
5. Uploads / preview
6. Confirmation list

## 對應 API

- `GET /v1/projects/{project_id}`
- `GET|POST /v1/projects/{project_id}/tasks`
- `GET|POST /v1/projects/{project_id}/runs`
- `GET /v1/projects/{project_id}/runs/{run_id}/stream`
- `GET|POST /v1/projects/{project_id}/uploads`
- `GET /v1/projects/{project_id}/confirmations`

## 行為規則

- UI 預設淺色模式
- run output 以 streaming event 顯示
- 上傳後先顯示 preview，再綁定任務
- destructive / gated actions 要進 confirmation drawer

## CLI 對應

同一組能力也可由 workspace CLI 操作：

- `amon workspace projects summary`
- `amon workspace definitions list|get|create|update|delete`
- `amon workspace runs list|get|create|resume|cancel|archive|stream`
- `amon workspace uploads list|add|get|preview|delete`
- `amon workspace confirmations list|approve|reject`
