# TaskGraph v3 Migration（已完成 cutover）

> TaskGraph v3 已完成 cutover。Amon 僅接受 `taskgraph.v3` payload，`TaskGraph3Runtime` 是唯一 production runtime。

## 完成狀態

- `run_graph` 與 graph template 執行入口只接受 `taskgraph.v3`
- single / self_critique / team 皆由原生 v3 payload builder 產生
- legacy runtime、legacy graph migrator、graph migrate CLI 已移除
- runtime 對非 v3 payload 採 fail-fast

## 維護原則

1. 不再新增 legacy/v2 graph 相容層。
2. 不再提供 legacy/v2 graph 遷移入口。
3. 若需擴充能力，必須直接擴充 TaskGraph v3 schema、payload builder 與 runtime。
4. 所有新測試都應直接針對 v3 payload 與 v3 runtime。

可搭配 `docs/refactor/taskgraph_v3_cutover.md` 與 `docs/refactor/taskgraph_v3_forbidden_legacy_refs.md` 做持續檢查。
