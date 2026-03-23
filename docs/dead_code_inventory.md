# Dead Code Inventory

## 目的

這份文件記錄本輪 dead-code elimination 的盤點結論，區分：

- `confirmed dead`：已確認沒有 repo 內引用，可直接移除
- `retained compatibility surface`：看起來舊，但目前仍有入口、測試或相容責任，不能硬刪

## 盤點方法

以 repo 內實際引用為準，檢查：

1. Python import / re-export
2. CLI / API / UI route 入口
3. static include
4. 現有測試覆蓋

## Confirmed Dead

### `src/amon/cli/plan.py`

- 狀態：已移除
- 原因：repo 內沒有任何 import / 呼叫 / 測試引用
- 觀察：`amon plan` 的真實 CLI 行為定義在 [src/amon/cli.py](D:/PycharmProjects/Amon/src/amon/cli.py)

### `src/amon/cli/run.py`

- 狀態：已移除
- 原因：repo 內沒有任何 import / 呼叫 / 測試引用
- 觀察：`amon run` 的真實 CLI 行為定義在 [src/amon/cli.py](D:/PycharmProjects/Amon/src/amon/cli.py)

## Retained Compatibility Surface

### `src/amon/graph_presets.py`

- 保留原因：仍由 [src/amon/core.py](D:/PycharmProjects/Amon/src/amon/core.py) 匯入，且仍被 template / importer 測試覆蓋
- 角色：template library 的 compatibility adapter，不是死碼

### `src/amon/planning/planner_llm.py`

- 保留原因：`generate_plan_with_llm` 仍由 [src/amon/planning/__init__.py](D:/PycharmProjects/Amon/src/amon/planning/__init__.py) re-export，且 [src/amon/core.py](D:/PycharmProjects/Amon/src/amon/core.py) 仍使用 `_minimal_plan`
- 角色：legacy planning fallback surface

### `src/amon/ui/event_stream_client.js`

- 保留原因：仍被 [src/amon/ui/index.html](D:/PycharmProjects/Amon/src/amon/ui/index.html) 載入，且有多個 UI 測試直接驗證
- 角色：現行 UI stream client，不是殘留檔案

### `src/amon/ui/project.html`

- 保留原因：仍被 UI smoke test 視為舊連結 redirect surface
- 角色：相容 redirect 到 `index.html#/context`

### `src/amon/ui/single.html`

- 保留原因：仍被 UI smoke test 視為舊連結 redirect surface
- 角色：相容 redirect 到 `index.html#/chat`

## 本輪新增的保護網

- [tests/test_legacy_characterization.py](D:/PycharmProjects/Amon/tests/test_legacy_characterization.py)

這份測試會鎖住：

1. `planner_llm._minimal_plan` 的 fallback graph 形狀
2. `AmonCore` 對 `graph_presets` compatibility adapter 的委派行為

## 下一輪建議

若要繼續清 legacy code，先針對下列模組補更細的 characterization tests，再判斷是否能移除：

- `src/amon/planning/planner_llm.py`
- `src/amon/graph_presets.py`
- `src/amon/ui/project.html`
- `src/amon/ui/single.html`
