# Template Authoring

## 目的

Template 是可重複套用的高階流程，不是 runtime primitive。它負責「流程形狀」，不負責低階 dispatcher 分支。

## 目前內建模板

- `single`
- `self_critique`
- `team`

來源檔案：

- [src/amon/templates/single.json](D:/PycharmProjects/Amon/src/amon/templates/single.json)
- [src/amon/templates/self_critique.json](D:/PycharmProjects/Amon/src/amon/templates/self_critique.json)
- [src/amon/templates/team.json](D:/PycharmProjects/Amon/src/amon/templates/team.json)

## 最小格式

```json
{
  "id": "single",
  "name": "single",
  "description": "單節點工作流程模板",
  "builder": "single",
  "parameters": {
    "prompt": {
      "type": "string",
      "required": true
    }
  },
  "defaults": {
    "mode": "single"
  }
}
```

## 欄位說明

- `id`：模板識別碼
- `name`：顯示名稱
- `description`：用途摘要
- `builder`：instantiate 時使用的 builder 名稱
- `parameters`：模板參數 contract
- `defaults`：預設模式或政策

## Authoring 準則

1. 模板只描述流程與參數，不內嵌 runtime-specific branch
2. LLM 節點仍需依執行結果發 streaming events
3. 若模板展開後需要 capability resolution，仍走 binder / compiler
4. 內建模板與自訂模板都應能 instantiate 成 workflow 或 compiled graph

## 範例

- [examples/templates/single.template.json](D:/PycharmProjects/Amon/examples/templates/single.template.json)
- [examples/templates/self_critique.template.json](D:/PycharmProjects/Amon/examples/templates/self_critique.template.json)
- [examples/templates/team.template.json](D:/PycharmProjects/Amon/examples/templates/team.template.json)
