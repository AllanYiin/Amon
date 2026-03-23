# Migration to `amon.manifest.v1`

## 適用對象

這份文件是給已經在用舊 graph authoring、preset 入口或直接手寫 `taskgraph.v3` 的維護者。

## 目標

把 source authoring 收斂到 `amon.manifest.v1`，但不放棄既有 `TaskGraph3Runtime` 投資。

## 遷移原則

1. 舊 `taskgraph.v3` graph 仍可被當作 compiled artifact 執行
2. 新 source 一律先寫 manifest，再經 binder / compiler 產出 `taskgraph.v3`
3. 舊 preset 入口保留一段時間，但內部已轉成 template instantiate
4. compile 失敗不得 fallback 成 runtime 猜測修補

## 從舊 graph authoring 遷移

### 舊寫法問題

- graph-level agent 與 node-level inline agent 同時存在
- planner prompt 與 runtime dispatch 的責任不一致
- `single` / `self_critique` / `team` 被硬編進 runtime/preset
- tool policy、approval、audit 沒有單一 source-of-truth

### 新寫法對應

| 舊概念 | 新概念 |
| --- | --- |
| inline `task_spec.agent` | `AgentProfile` + `ExecutorBinding(type=llm)` |
| inline `tool` payload | `ExecutorBinding(type=tool)` + `ToolPolicy` |
| inline `sandbox_run` | `ExecutorBinding(type=sandbox)` |
| graph preset | `Template` |
| runtime 猜測 assignment | binder resolve capability -> executor |

## 最小遷移步驟

1. 把 task 工作語意抽成 `TaskDefinition`
2. 把模型角色抽成 `AgentProfile`
3. 把執行方式抽成 `ExecutorBinding`
4. 用 workflow node 只保留 `task_ref` + `executor_ref`
5. 若是 preset 流程，改用 template
6. 用 compiler 產出 compiled `taskgraph.v3`

## 範例

source manifest 範例見 [examples/manifests/spec_pipeline.manifest.json](D:/PycharmProjects/Amon/examples/manifests/spec_pipeline.manifest.json)。

## 舊 preset 遷移

### `single`

- 舊：preset branch
- 新： [examples/templates/single.template.json](D:/PycharmProjects/Amon/examples/templates/single.template.json)

### `self_critique`

- 舊：preset branch
- 新： [examples/templates/self_critique.template.json](D:/PycharmProjects/Amon/examples/templates/self_critique.template.json)

### `team`

- 舊：preset branch
- 新： [examples/templates/team.template.json](D:/PycharmProjects/Amon/examples/templates/team.template.json)

## 驗證遷移成功

```bash
python -m unittest tests.contract.test_manifest_contract
python -m unittest tests.contract.test_compiled_graph_contract
```

若 workflow 仍出現 unresolved refs，compiler 會 fail-fast。
