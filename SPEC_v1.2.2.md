# Amon Spec v1.2.2

## 摘要

Amon vNext 採單一 source-of-truth：

`amon.manifest.v1 -> binder / compiler -> compiled taskgraph.v3 -> TaskGraph3Runtime`

這份版本對應目前 repo 在 Stage 0 到 Stage 8 的落地狀態，目標不是推翻既有 runtime，而是把 authoring、binding、execution、template、trigger 的責任切乾淨。

## 核心原則

1. 手寫與持久化來源格式統一為 `amon.manifest.v1`
2. runtime 正式輸入仍為 compiled `taskgraph.v3`
3. planner 只產出 logical tasks / dependencies / required capabilities / acceptance criteria
4. source manifest node 僅允許 `task_ref` 與 `executor_ref`
5. executor type 僅允許 `llm | tool | sandbox | human_gate | subgraph`
6. `single`、`self_critique`、`team` 為 template，不是 runtime primitive
7. tool invocation 必須標註 `deterministic | delegated`
8. 所有 LLM 輸出必須 streaming
9. 所有 run 必須有 snapshot pins 與 trigger metadata
10. unresolved refs 必須 compile-time fail-fast

## 目前模組狀態

### Canonical model

- manifest model： [src/amon/domain/manifest.py](D:/PycharmProjects/Amon/src/amon/domain/manifest.py)
- entities： [src/amon/domain/entities](D:/PycharmProjects/Amon/src/amon/domain/entities)
- repositories： [src/amon/storage/repositories](D:/PycharmProjects/Amon/src/amon/storage/repositories)

### Planner / Binder / Compiler

- planner： [src/amon/planning/planner_vnext.py](D:/PycharmProjects/Amon/src/amon/planning/planner_vnext.py)
- binder： [src/amon/planning/binder.py](D:/PycharmProjects/Amon/src/amon/planning/binder.py)
- compiler： [src/amon/planning/compiler_vnext.py](D:/PycharmProjects/Amon/src/amon/planning/compiler_vnext.py)

### Runtime vNext

- dispatcher： [src/amon/runtime_vnext/executor_dispatcher.py](D:/PycharmProjects/Amon/src/amon/runtime_vnext/executor_dispatcher.py)
- tool policy： [src/amon/runtime_vnext/tool_policy_engine.py](D:/PycharmProjects/Amon/src/amon/runtime_vnext/tool_policy_engine.py)
- checkpoint / resume： [src/amon/runtime_vnext](D:/PycharmProjects/Amon/src/amon/runtime_vnext)

### Templates

- library： [src/amon/templates/library.py](D:/PycharmProjects/Amon/src/amon/templates/library.py)
- built-ins： [src/amon/templates/single.json](D:/PycharmProjects/Amon/src/amon/templates/single.json)、 [src/amon/templates/self_critique.json](D:/PycharmProjects/Amon/src/amon/templates/self_critique.json)、 [src/amon/templates/team.json](D:/PycharmProjects/Amon/src/amon/templates/team.json)

### Trigger integration

- hooks / schedules / jobs 轉發： [src/amon/triggers](D:/PycharmProjects/Amon/src/amon/triggers)
- daemon runner： [src/amon/daemon/runner.py](D:/PycharmProjects/Amon/src/amon/daemon/runner.py)

### Local API / CLI / UI

- HTTP server： [src/amon/ui_server.py](D:/PycharmProjects/Amon/src/amon/ui_server.py)
- workspace CLI： [src/amon/interfaces/cli/commands](D:/PycharmProjects/Amon/src/amon/interfaces/cli/commands)
- workspace UI： [src/amon/ui/index.html](D:/PycharmProjects/Amon/src/amon/ui/index.html)

## 物件邊界

### WorkflowDefinition

只負責節點順序、依賴、條件路由與輸入輸出映射，不直接攜帶 inline agent/tool payload。

### TaskDefinition

只描述工作語意、input/output contract、acceptance criteria、required capabilities、side effect class。

### AgentProfile

只描述 LLM 角色：system prompt、skills、model policy、memory policy、output style。

### ExecutorBinding

是 logical task 與實際執行方式的唯一橋樑。runtime dispatcher 只看這裡，不再掃多個散落欄位。

### ToolPolicy

定義 allowed tools、allowed paths、network、delegation、side effect ceiling、approval rules。

### Template

高階流程範本，可 instantiate 成 workflow；模板本身不是 runtime primitive。

## Run / Event / Audit

### Run 狀態

`created -> planning -> binding -> compiled -> queued -> running -> waiting_confirmation -> succeeded`

並支援：

- `paused`
- `retrying`
- `failed`
- `cancelled`
- `rolled_back`
- `archived`

### 事件契約

核心 streaming 事件：

- `run.created`
- `run.phase_changed`
- `node.started`
- `node.chunk`
- `node.tool_requested`
- `node.confirmation_requested`
- `node.confirmation_resolved`
- `node.succeeded`
- `node.failed`
- `run.succeeded`
- `run.failed`
- `run.resumed`

### Tool audit

每次工具呼叫都需留下：

- `invocation_mode`
- `selected_by`
- `approval_state`
- `side_effect_class`
- `run_id`
- `node_id`

## Trigger 規則

1. hook / schedule / job 只能產生標準 run request
2. trigger metadata 必須進 run snapshot
3. dedupe / cooldown / backpressure 必須在 trigger 層生效
4. trigger 不得繞過 binder / compiler / runtime 直接執行低階動作

## Upload / Preview 規則

- 所有 upload 都必須有 preview 或明確 fallback
- 文字檔提供 inline preview
- 圖片保留寬高
- PDF 目前先 metadata fallback
- zoom 一律維持 aspect ratio

## 測試覆蓋

已落地的測試類型：

- unit：planner / binder / compiler / runtime policy / checkpoint
- contract：manifest / compiled graph
- integration：workspace routes / CLI / trigger-to-run / resume / upload preview / confirmation gate
- smoke：workspace UI / examples
- failure injection：stream reconnect / preview fallback / tool denied

## 已知缺口

1. repo 全量 `unittest discover` 仍可能逾時
2. `amon ui --port 8000` 在目前 CLI 路徑下會立即結束，不會保持前景 server
3. PDF 首頁影像 preview 尚未接真實 renderer

詳見 [docs/known_limits.md](D:/PycharmProjects/Amon/docs/known_limits.md)。
