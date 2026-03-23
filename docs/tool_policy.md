# Tool Policy

## 目的

Tool policy 把「能不能用工具」從 prompt 與 runtime 細節中抽離，變成可審計、可確認、可測試的規則。

## 兩種 invocation mode

### deterministic

由 workflow author 或 template 明確指定工具與參數模板。

適用：

- 固定寫檔
- 匯出
- sandbox 步驟
- 可預測轉換

### delegated

由 LLM 在 ToolPolicy 允許範圍內選擇工具。

適用：

- read-only 搜尋
- 探索性資料蒐集
- 低副作用查詢

## 核心欄位

- `allowed_tools`
- `allowed_paths`
- `allow_network`
- `delegated_allowed`
- `side_effect_ceiling`
- `approval_rules`

## side effect class

從低到高：

1. `read_only`
2. `workspace_write`
3. `destructive_write`
4. `external_network`
5. `sandbox_exec`

## 預設規則

- `read_only`：可直接 allow
- `workspace_write`：至少要有 preview / diff
- `destructive_write`：必須 confirmation
- `external_network`：預設 deny，需 policy 顯式允許
- `sandbox_exec`：必須 confirmation

## Audit record

每次 tool call 都要留下：

```json
{
  "run_id": "r1",
  "node_id": "n1",
  "tool_name": "filesystem.write",
  "invocation_mode": "deterministic",
  "selected_by": "workflow",
  "approval_state": "approved",
  "side_effect_class": "workspace_write"
}
```

## 相關文件

- 規格總覽： [SPEC_v1.2.2.md](D:/PycharmProjects/Amon/SPEC_v1.2.2.md)
- 實作： [src/amon/runtime_vnext/tool_policy_engine.py](D:/PycharmProjects/Amon/src/amon/runtime_vnext/tool_policy_engine.py)
