# Runtime vNext

## 架構位置

vNext runtime 不是第二套完整 runtime，而是接在既有 `TaskGraph3Runtime` 前的 authoring / policy / orchestration 整理層。

執行路徑：

`manifest -> binder -> compiler -> compiled.taskgraph.v3.json -> TaskGraph3Runtime`

## 核心元件

- dispatcher： [src/amon/runtime_vnext/executor_dispatcher.py](D:/PycharmProjects/Amon/src/amon/runtime_vnext/executor_dispatcher.py)
- llm executor： [src/amon/runtime_vnext/llm_executor.py](D:/PycharmProjects/Amon/src/amon/runtime_vnext/llm_executor.py)
- tool executor： [src/amon/runtime_vnext/tool_executor.py](D:/PycharmProjects/Amon/src/amon/runtime_vnext/tool_executor.py)
- sandbox executor： [src/amon/runtime_vnext/sandbox_executor.py](D:/PycharmProjects/Amon/src/amon/runtime_vnext/sandbox_executor.py)
- confirmation： [src/amon/runtime_vnext/confirmation_service.py](D:/PycharmProjects/Amon/src/amon/runtime_vnext/confirmation_service.py)
- audit： [src/amon/runtime_vnext/audit_log.py](D:/PycharmProjects/Amon/src/amon/runtime_vnext/audit_log.py)

## 支援的 executor type

- `llm`
- `tool`
- `sandbox`
- `human_gate`

## Streaming

所有 LLM 文字輸出都要以 `node.chunk` 形式送出。這包含：

- planner LLM
- workflow 中的 LLM node
- review / critique node
- template 展開後的 LLM node

run stream endpoint：

- `GET /v1/projects/{project_id}/runs/{run_id}/stream`

目前已支援 `Last-Event-ID` 續接 replay。

## Checkpoint / Resume

run 會將 checkpoint、confirmation queue、snapshot manifest、compiled graph 釘在 `.amon/runs/<run_id>/` 下。

相關文件：

- [src/amon/runtime_vnext/checkpoint_store.py](D:/PycharmProjects/Amon/src/amon/runtime_vnext/checkpoint_store.py)
- [src/amon/runtime_vnext/resume_service.py](D:/PycharmProjects/Amon/src/amon/runtime_vnext/resume_service.py)

## Trigger integration

hooks / schedules / jobs 不再直接做低階行為，而是統一產生標準 run request。

相關模組：

- [src/amon/triggers/hook_service.py](D:/PycharmProjects/Amon/src/amon/triggers/hook_service.py)
- [src/amon/triggers/schedule_service.py](D:/PycharmProjects/Amon/src/amon/triggers/schedule_service.py)
- [src/amon/triggers/job_service.py](D:/PycharmProjects/Amon/src/amon/triggers/job_service.py)
