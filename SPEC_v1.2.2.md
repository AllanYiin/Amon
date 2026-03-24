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

## Validation Layers

manifest validation 分成三層：

1. authoring validation
2. bound-workflow validation
3. compile validation

規則如下：

- authoring 階段允許 `node.executor_ref` 為空；若有提供，才要求可 resolve
- authoring 階段必須 fail-fast 檢查 workflow 結構：duplicate node id、missing depends_on、self-dependency、cycle
- binder 綁定前跑 authoring validation，綁定後跑 bound validation
- compiler 只接受 bound-valid workflow；未綁定 workflow 必須在 compile 前拒絕
- `validate_references()` 保留為相容 wrapper，但語意等同 authoring validation

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

目前 support matrix：

- spec / domain 可宣告：`llm | tool | sandbox | human_gate | subgraph`
- binder / compiler / runtime 已接通：`llm | tool | sandbox | human_gate`
- `subgraph` 目前必須在 binder 或 compiler fail-fast，錯誤碼固定為 `AMON_EXECUTOR_TYPE_001`

### CompiledNodeMetadata

compiled `taskgraph.v3` node metadata 必須有單一 canonical contract，至少包含：

- `task_ref` / `task_version`
- `executor_ref` / `executor_version` / `executor_type`
- `streaming_required`
- `required_capabilities`
- `tool_invocation_mode`
- serialized `tool_policy`
- `agent_profile_ref` / `agent_profile_version`
- `timeout_s` / `approval_policy` / `retry_policy`

runtime 僅能透過這份 compiled metadata contract 讀取 execution metadata；不得在 executor 內散落 `metadata.get("...")`。

相容性規則：

- legacy compiled graph 若缺少 `executor_type`，runtime 可依 `task_spec.executor` fallback 推斷 `llm`、`tool`、`sandbox`
- 這個 fallback 僅作 backward compatibility，用於舊 graph；新 graph 一律由 compiler 顯式寫入 canonical metadata

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
