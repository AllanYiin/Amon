# APSM 決策樹

先做 `references/usage_scene_decision_tree.md` 的使用情境判定，再做這份 APSM 技術選型。

`usage_scene` 決定專案要多黑盒、要多穩、要多工程化；APSM 只決定技術實作型態與目錄模板。不要把兩者混在一起。

這份決策樹只負責**篩選與選型**，不直接決定細部資料夾。決策結果必須輸出成 `project.config.json`，再由完整矩陣去對應目錄模板與 validator 規則。

## 使用原則

1. 先把需求整理到根目錄 `specs/requirements.md`，再回答前端型態、部署/組織方式與後端型態。
2. 決策樹的輸出是 `archetype`、`architecture`、`frontend`、`backend`。
3. 細部目錄結構請回到 `references/directory_structure_recommendations.md` 查對應模板。
4. 若需求落在決策樹之外，不要猜；應明確標示 unsupported，再擴充矩陣。

## 決策樹

### Q1. 是否需要獨立前端？

- 不需要，只有 API / webhook / service：
  - 若後端是 Python
    - 輸出：`service_api + single_service + none + python_api`
    - 模板：`C1`
  - 若後端是 Node
    - 輸出：`service_api + single_service + none + node_api`
    - 模板：`C2`

- 需要 Python template rendering（Flask/FastAPI/Jinja/Django templates）：
  - 輸出：`python_fullstack + single_service + python_templates + python_api`
  - 模板：`B3`

- 需要 Node SPA（React/Vue/Vite）：
  - 進入 Q2

- 需要 Node SSR / MPA（Next/Nuxt）：
  - 進入 Q2

### Q2. 前後端要怎麼組織？

- 前後端分目錄、可獨立部署：
  - 若前端是 `node_spa`
    - 後端 Python：`web_app + separated + node_spa + python_api` → `A1`
    - 後端 Node：`web_app + separated + node_spa + node_api` → `A2`
  - 若前端是 `node_ssr`
    - 後端 Python：`web_app + separated + node_ssr + python_api` → `A3`
    - 後端 Node：`web_app + separated + node_ssr + node_api` → `A4`

- 單一 repo，但前後端仍分 `src/server` / `src/web`：
  - 若前端是 `node_spa`
    - 後端 Python：`monorepo + monorepo + node_spa + python_api` → `B1`
    - 後端 Node：`monorepo + monorepo + node_spa + node_api` → `B2`
  - 若前端是 `node_ssr`
    - 後端 Python：`monorepo + monorepo + node_ssr + python_api` → `B5`
    - 後端 Node：`monorepo + monorepo + node_ssr + node_api` → `B6`

- 單體 fullstack，不拆成 `src/server` / `src/web` 兩塊：
  - 只接受 `node_ssr + node_api`
    - 輸出：`fullstack_app + single_service + node_ssr + node_api`
    - 模板：`B4`
  - 若是 `node_spa`，不建議硬塞進 single-service；請改走 `separated` 或 `monorepo`

## 12 組完整輸出清單

| 模板 | `archetype` | `architecture` | `frontend` | `backend` |
|---|---|---|---|---|
| A1 | `web_app` | `separated` | `node_spa` | `python_api` |
| A2 | `web_app` | `separated` | `node_spa` | `node_api` |
| A3 | `web_app` | `separated` | `node_ssr` | `python_api` |
| A4 | `web_app` | `separated` | `node_ssr` | `node_api` |
| B1 | `monorepo` | `monorepo` | `node_spa` | `python_api` |
| B2 | `monorepo` | `monorepo` | `node_spa` | `node_api` |
| B3 | `python_fullstack` | `single_service` | `python_templates` | `python_api` |
| B4 | `fullstack_app` | `single_service` | `node_ssr` | `node_api` |
| B5 | `monorepo` | `monorepo` | `node_ssr` | `python_api` |
| B6 | `monorepo` | `monorepo` | `node_ssr` | `node_api` |
| C1 | `service_api` | `single_service` | `none` | `python_api` |
| C2 | `service_api` | `single_service` | `none` | `node_api` |
