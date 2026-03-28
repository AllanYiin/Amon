# 全專案共通硬規則

以下所有檔案路徑都以**目標專案根目錄的相對路徑**表示；只有在明確寫「此 skill 內」時，才是指 skill 自己資料夾內的相對路徑。

## APSM v1: 先做使用情境判定，再做技術選型，不要直接挑目錄模板

在 APSM 之前，先完成 `references/usage_scene_decision_tree.md` 的使用情境判定。

- `usage_scene` 決定交付摩擦、穩定度、工程化程度與文件深度
- APSM 決定技術實作型態與細部目錄模板
- 兩者一起落地到根目錄 `project.config.json`
- 根目錄 `AGENTS.md` 必須由「核心規則 + 使用情境規則 + 技術補充規則 + 專案特例」組成

> 注意：使用情境的 A/B/C/D，和 APSM 模板的 A1/B3/C2 不是同一套編碼。

建議順序：

1. 先把需求規格寫進根目錄 `specs/requirements.md`。
2. 先用 `references/usage_scene_decision_tree.md` 判定 `usage_scene` 與 `project_profile`，並生成根目錄 `AGENTS.md`。
3. 再用 `references/apsm_decision_tree.md` 決定 `archetype` / `architecture` / `frontend` / `backend`。
4. 把場景與技術選型一起寫進根目錄 `project.config.json`，並標記 `apsm_version`。
5. 用 `scripts/apsm_validate.py` 驗證 config、`AGENTS.md` 與目錄是否對齊。
6. 再依選到的模板建立實際目錄。

APSM（AI Project Structure Model）是這個 skill 的 machine-readable 目錄規劃模型。這份文件的 A/B/C 各節是**目錄模板庫**。以下段落只保留 APSM 技術矩陣說明；實際流程以上方「建議順序」為準。

1. 先把需求規格寫進根目錄 `specs/requirements.md`。
2. 再依 `references/apsm_decision_tree.md` 做篩選，決定技術選型與專案類型。
3. 把選型結果寫進根目錄 `project.config.json`，並標記 `apsm_version`。
4. 用 `scripts/apsm_validate.py` 驗證 config 與骨架。
5. 再依選型映射到對應模板。

### APSM 的兩層模型

`archetype` 是入口分類，`architecture/frontend/backend` 是精確技術組合。這兩層要同時存在，但責任不同：

- `archetype`：給 AI 與新手快速決策，不要直接暴露 A1/B3 之類模板代號。
- `architecture/frontend/backend`：給 validator、launcher、README 與後續 agent 做 deterministic 判讀。

目前這個 skill 採用的 archetype 對照如下：

| `archetype` | 說明 | 對應組合 |
|---|---|---|
| `web_app` | 前後端分離的 Web App | `separated + node_spa/node_ssr + python_api/node_api` |
| `monorepo` | 前後端都放在 `src/` | `monorepo + node_spa + python_api/node_api` |
| `python_fullstack` | Python template rendering | `single_service + python_templates + python_api` |
| `fullstack_app` | 此 skill 為相容既有 B4 模板保留的延伸 archetype | `single_service + node_ssr + node_api` |
| `service_api` | API-only 單體服務 | `single_service + none + python_api/node_api` |

### 技術選型最少要決定的五個欄位

- `architecture`
  - `separated`：前後端分目錄，生命周期可獨立
  - `monorepo`：單一 repo，但用 `src/server`、`src/web` 分區
  - `single_service`：單一服務或 Python 模板渲染，不拆前後端
- `frontend`
  - `node_spa`：React / Vue / Vite 類互動式前端
  - `node_ssr`：Next / Nuxt 類 SSR / MPA
  - `python_templates`：Flask / FastAPI / Django 模板渲染
  - `none`：沒有獨立前端（此文件目前不展開純 CLI/純 API 模板）
- `backend`
  - `python_api`
  - `node_api`
  - `none`

### 選型原則

- 預設 Python-first；只有在需要瀏覽器級前端體驗、SSR 能力或明確的 Node 生態時才引入 Node。
- 若只是簡單內部工具、模板頁或表單流程，優先 `single_service + python_templates + python_api`。
- 若前後端要獨立啟動/部署，或 API 必須單獨存在，選 `separated`。
- 若要單一 repo 但又需要明確區分前後端，選 `monorepo`。
- 若需求不在這份文件的 canonical 組合內，先回頭修正選型，不要臨時發明新的 root 命名規則。

### `project.config.json` 範例

```json
{
  "name": "my-vibe-app",
  "usage_scene": "scene_b_shared_tool",
  "project_profile": {
    "user_type": "small_team",
    "usage_duration": "occasional",
    "change_frequency": "occasional",
    "failure_cost": "multi_user_disruption"
  },
  "apsm_version": "1.0",
  "archetype": "web_app",
  "architecture": "separated",
  "frontend": "node_spa",
  "backend": "python_api",
  "version": "0.1.0"
}
```

### APSM 檢核方式

建立骨架後，必須執行：

```bash
python scripts/apsm_validate.py --project <target-project>
```

檢核內容至少包含：

- `project.config.json` 是否存在且為合法 JSON
- `apsm_version` 是否支援
- `archetype` 是否存在且與 `architecture/frontend/backend` 相符
- `architecture/frontend/backend` 是否為支援組合
- 根目錄固定檔案是否存在
- 對應模板的關鍵目錄與啟動入口是否存在
- `.env` 的必要 key 是否齊全
- 若已執行過 launcher，`.runtime/ports.json` 與 `.runtime/launcher_state.json` 也要合法

交付前再補跑一次嚴格模式：

```bash
python scripts/apsm_validate.py --project <target-project> --strict
```

### 選型對應模板

| `architecture` | `frontend` | `backend` | 套用模板 |
|---|---|---|---|
| `separated` | `node_spa` | `python_api` | A1 |
| `separated` | `node_spa` | `node_api` | A2 |
| `separated` | `node_ssr` | `python_api` | A3 |
| `separated` | `node_ssr` | `node_api` | A4 |
| `monorepo` | `node_spa` | `python_api` | B1 |
| `monorepo` | `node_spa` | `node_api` | B2 |
| `monorepo` | `node_ssr` | `python_api` | B5 |
| `monorepo` | `node_ssr` | `node_api` | B6 |
| `single_service` | `python_templates` | `python_api` | B3 |
| `single_service` | `node_ssr` | `node_api` | B4 |
| `single_service` | `none` | `python_api` | C1 |
| `single_service` | `none` | `node_api` | C2 |
### 根目錄固定存在

```
project-root/
├─ project.config.json     # ✅ 先宣告選型，再規劃目錄
├─ .venv/                 # ✅ 永遠在根目錄
├─ .runtime/              # ✅ launcher 產生的 runtime metadata
│  ├─ ports.json
│  └─ launcher_state.json
├─ logs/                  # ✅ 統一 log 位置
│  ├─ backend.log
│  ├─ frontend.log
│  └─ launcher.log
├─ scripts/
│  ├─ project_launcher.py # ✅ 先由此 skill 內的 scripts/project_launcher.py 寫入到目標專案
│  └─ apsm_validate.py    # ✅ APSM 結構檢核器
├─ specs/
│  └─ requirements.md     # ✅ Step 1 產出的需求規格唯一落點
├─ requirements.txt        # ✅ 永遠在根目錄（即使是 Node-only 也保留規範）
├─ run_app.bat             # ✅ 永遠在根目錄（cmd/bat）
├─ run_app.command         # ✅ 永遠在根目錄（macOS）
├─ run_app.sh              # ✅ 永遠在根目錄（Linux）
├─ .env                    # ✅ 我建議：port & 服務位址的 single source of truth（不進版控）
├─ .env.example            # ✅ port 範本（進版控）
├─ README.md
├─ AGENTS.md
└─ todo.md
```

所有以下模板都繼承上方共通根目錄固定檔案，包含 `specs/requirements.md`、`project.config.json`、`AGENTS.md`、`README.md`、`todo.md` 與 launcher / validator。

### Port 資訊“維護位置”統一規範（強烈建議）

### APSM Runtime 與 lifecycle

- `project_launcher.py` 應 seed `.runtime/ports.json` 與 `.runtime/launcher_state.json`，讓 validator、launcher 與後續 agent 都能用機器可讀資料看懂目前狀態。
- `ports.json` 至少要反映目前專案需要的 port key，例如 `backend_port`、`frontend_port`。
- `launcher_state.json` 至少要有 `status`、`last_event`、`updated_at`；不能只有空 JSON。
- `logs/` 應維持 deterministic 位置；至少要有 `launcher.log`，有後端時要有 `backend.log`，有 Node 前端時要有 `frontend.log`。
- 為了維持這個 skill 既有的跨平台雙擊體驗，目前仍保留 `run_app.bat` / `run_app.command` / `run_app.sh` 三入口，不跟著 PDF 直接改成單一 `run_app`。

* **唯一真相：根目錄 `.env`**
* 不同服務讀取各自的 key（但都來自同一個 `.env` 範本）
* 若要做動態 port，`.env` 只應保存預設值或策略；真正啟動後的最終 port 應另寫入 launcher runtime 狀態，而不是假裝 `.env` 永遠等於實際值

建議 key（你可以照抄這些名稱當團隊規範）：

* `BACKEND_HOST=127.0.0.1`
* `BACKEND_PORT=8000`
* `FRONTEND_HOST=127.0.0.1`
* `FRONTEND_PORT=5173`（Vite 常用）
* `FRONTEND_URL=http://127.0.0.1:5173`
* `API_BASE_URL=http://127.0.0.1:8000`

### 動態 Port 規範（零開發經驗使用者優先）

* 不要先掃描一個空 port 再假設仍可用；應由服務實際綁定，之後回讀最終 port。
* 啟動器必須把最終 port 同步到：
  * 顯示給使用者的 URL
  * 前端 `API_BASE_URL`
  * `logs/` 或 runtime 狀態檔
  * 自動開瀏覽器的目標網址
* 若做不到完整同步，寧可固定使用設定值並在衝突時清楚報錯，也不要做半套遞補。
* 自動開瀏覽器前應先做 readiness check；否則只輸出 URL，不要直接打開瀏覽器。

---

# A) 前後端分離（根目錄必有 `backend/`、`frontend/`）

## A1. 前端 SPA（Node.js） + 後端 Python（API）

### 目錄

```
project-root/
├─ backend/
│  ├─ app/                        # ✅ 不用 src，多一層就煩
│  │  ├─ __init__.py
│  │  ├─ __main__.py              # ✅ 後端啟動進入點（固定）
│  │  ├─ main.py                  # app 組裝/建立
│  │  ├─ api/
│  │  ├─ core/                    # 設定/讀 env / logging
│  │  ├─ services/
│  │  ├─ models/
│  │  ├─ schemas/
│  │  ├─ db/
│  │  └─ utils/
│  └─ tests/
│
├─ frontend/
│  ├─ src/
│  ├─ public/
│  ├─ package.json                # ✅ 前端啟動入口（看 scripts）
│  └─ (lockfile)
│
├─ .venv/
├─ specs/
│  └─ requirements.md
├─ requirements.txt
├─ run_app.bat
├─ .env
└─ .env.example
```

### 啟動進入點（規範寫死）

* **後端啟動進入點**：`backend/app/__main__.py`（建議啟動方式固定成 `python -m app`）
* **前端啟動進入點**：`frontend/package.json` 的 `scripts.dev`（例如 `vite` / `next dev` 之類）

### Port 資訊維護在哪

* **維護位置**：根目錄 `.env`
* **後端讀取**：`BACKEND_HOST`, `BACKEND_PORT`（由 `backend/app/core/config.py` 或同等模組集中讀取）
* **前端 dev server port**：`FRONTEND_PORT`
* **前端呼叫 API 的 base url**：`API_BASE_URL`

---

## A2. 前端 SPA（Node.js） + 後端 Node.js（API）

### 目錄

```
project-root/
├─ backend/
│  ├─ src/
│  │  ├─ server.ts                # ✅ 後端啟動進入點（固定）
│  │  ├─ api/
│  │  ├─ core/                    # 設定/讀 env / logging
│  │  ├─ services/
│  │  ├─ models/
│  │  └─ utils/
│  ├─ package.json                # ✅ 後端啟動入口（看 scripts）
│  └─ tests/
│
├─ frontend/
│  ├─ src/
│  ├─ public/
│  ├─ package.json                # ✅ 前端啟動入口（看 scripts）
│  └─ (lockfile)
│
├─ .venv/
├─ specs/
│  └─ requirements.md
├─ requirements.txt
├─ run_app.bat
├─ .env
└─ .env.example
```

### 啟動進入點

* **後端啟動進入點（檔案）**：`backend/src/server.ts`（或 `server.js`，但你要固定一個）
* **後端啟動入口（命令來源）**：`backend/package.json` 的 `scripts.dev` / `scripts.start`
* **前端啟動入口**：`frontend/package.json` 的 `scripts.dev`

### Port 資訊維護在哪

* **維護位置**：根目錄 `.env`
* **後端讀取**：`BACKEND_PORT`（Node 慣例用 `PORT`，但你要規範一致也行：程式內把 `BACKEND_PORT` fallback 到 `PORT`）
* **前端讀取**：`FRONTEND_PORT`, `API_BASE_URL`

---

## A3. 前端非 SPA（Node SSR/MPA，例如 Next/Nuxt） + 後端 Python（API）

> 這種通常是「前端是會在伺服器端渲染的 Node app」，再去打 Python API。

### 目錄

```
project-root/
├─ backend/
│  ├─ app/
│  │  ├─ __main__.py              # ✅ 後端啟動進入點
│  │  ├─ main.py
│  │  ├─ api/
│  │  └─ core/
│  └─ tests/
│
├─ frontend/
│  ├─ app/ or pages/              # 依 Next/Nuxt 架構
│  ├─ package.json                # ✅ 前端 SSR 啟動入口（scripts）
│  ├─ next.config.* / nuxt.config.*
│  └─ (lockfile)
│
├─ .venv/
├─ specs/
│  └─ requirements.md
├─ requirements.txt
├─ run_app.bat
├─ .env
└─ .env.example
```

### 啟動進入點

* **Python 後端**：`backend/app/__main__.py`
* **Node SSR 前端**：`frontend/package.json` 的 `scripts.dev` / `scripts.start`（Next/Nuxt 的 server 入口由框架接管）

### Port 資訊維護在哪

* **維護位置**：根目錄 `.env`
* **SSR 前端 port**：`FRONTEND_PORT`
* **Python API port**：`BACKEND_PORT`
* **SSR 端呼叫 API 的位址**：`API_BASE_URL`（SSR 會在 server 端打 API，更需要這個別寫死）

---

## A4. 前端非 SPA（Node SSR/MPA） + 後端 Node.js（API）

### 目錄

```
project-root/
├─ backend/
│  ├─ src/
│  │  └─ server.ts                # ✅ 後端啟動進入點
│  ├─ package.json
│  └─ tests/
│
├─ frontend/
│  ├─ app/ or pages/
│  ├─ package.json                # ✅ SSR 前端啟動入口
│  └─ (lockfile)
│
├─ .venv/
├─ specs/
│  └─ requirements.md
├─ requirements.txt
├─ run_app.bat
├─ .env
└─ .env.example
```

### 啟動進入點

* **Node API 後端**：`backend/src/server.ts`
* **Node SSR 前端**：`frontend/package.json`（scripts）

### Port 資訊維護在哪

* **維護位置**：根目錄 `.env`
* **API**：`BACKEND_PORT`
* **SSR 前端**：`FRONTEND_PORT`
* **API base**：`API_BASE_URL`

---

# B) 不分離（根目錄為 `src/`，沒有 `backend/`、`frontend/`）

你要的是「不分離根目錄為 `src`」，所以我在不分離全部用 `src/` 當代碼根，再用子目錄區分“server / web / templates”。

---

## B1. 前端 SPA（Node） + 後端 Python（API）同 repo（但不叫 backend/frontend）

### 目錄

```
project-root/
├─ src/
│  ├─ server/                     # Python 後端
│  │  ├─ app/
│  │  │  ├─ __main__.py           # ✅ 後端啟動進入點
│  │  │  ├─ main.py
│  │  │  ├─ api/
│  │  │  └─ core/
│  │  └─ tests/
│  │
│  └─ web/                        # Node SPA 前端
│     ├─ src/
│     ├─ public/
│     ├─ package.json             # ✅ 前端啟動入口（scripts）
│     └─ (lockfile)
│
├─ .venv/
├─ specs/
│  └─ requirements.md
├─ requirements.txt
├─ run_app.bat
├─ .env
└─ .env.example
```

### 啟動進入點

* **Python 後端**：`src/server/app/__main__.py`
* **Node 前端**：`src/web/package.json`（scripts）

### Port 資訊維護在哪

* **維護位置**：根目錄 `.env`
* **後端**：`BACKEND_PORT`
* **前端**：`FRONTEND_PORT`
* **API base**：`API_BASE_URL`

---

## B2. 前端 SPA（Node） + 後端 Node（API）同 repo（不分離）

### 目錄

```
project-root/
├─ src/
│  ├─ server/                     # Node 後端
│  │  ├─ server.ts                # ✅ 後端啟動進入點（固定）
│  │  ├─ api/
│  │  ├─ core/
│  │  ├─ services/
│  │  └─ models/
│  │
│  └─ web/                        # Node SPA 前端
│     ├─ src/
│     ├─ public/
│     ├─ package.json             # ✅ 前端啟動入口
│     └─ (lockfile)
│
├─ package.json                   # 可選：若你要在根目錄做 workspace 統管
├─ .venv/
├─ specs/
│  └─ requirements.md
├─ requirements.txt
├─ run_app.bat
├─ .env
└─ .env.example
```

### 啟動進入點

* **Node 後端**：`src/server/server.ts`（實際啟動命令由 `package.json scripts` 統一）
* **Node 前端**：`src/web/package.json`

### Port 資訊維護在哪

* **維護位置**：根目錄 `.env`
* **後端**：`BACKEND_PORT`
* **前端**：`FRONTEND_PORT`
* **API base**：`API_BASE_URL`

---

## B3. 前端非 SPA（Python 模板渲染：MPA/SSR） + 後端 Python（同一個）

> 這裡「前端是 Python」的意思就是：HTML 模板 & 靜態資源由 Python 伺服器渲染/輸出，不需要 Node 來跑前端框架。

### 目錄

```
project-root/
├─ src/
│  ├─ app/                         # Python（同時扮演後端 + SSR/模板前端）
│  │  ├─ __main__.py               # ✅ 啟動進入點
│  │  ├─ main.py
│  │  ├─ api/                      # 若同時也提供 API
│  │  ├─ core/
│  │  ├─ services/
│  │  ├─ models/
│  │  ├─ templates/                # ✅ HTML 模板（非 SPA）
│  │  └─ static/                   # ✅ CSS/JS/圖片（非 SPA）
│  └─ tests/
│
├─ .venv/
├─ specs/
│  └─ requirements.md
├─ requirements.txt
├─ run_app.bat
├─ .env
└─ .env.example
```

### 啟動進入點

* **唯一啟動進入點**：`src/app/__main__.py`

### Port 資訊維護在哪

* **維護位置**：根目錄 `.env`
* **此模式通常只需要一個 port**：用 `BACKEND_PORT`（或你也可以改名 `APP_PORT`，但我建議仍用 `BACKEND_PORT` 一致）

---

## B4. 前端非 SPA（Node SSR：Next/Nuxt 等） + 後端 Node（同一個 BFF/全端）

> 這裡是「前端非 SPA」但仍然是 Node：SSR 框架本身就同時扮演前端渲染與後端（可做 BFF）。

### 目錄

```
project-root/
├─ src/
│  └─ web/                         # Node SSR 全端（Next/Nuxt）
│     ├─ app/ or pages/
│     ├─ server/                   # 可選：自訂 server（若你不用框架內建）
│     ├─ package.json              # ✅ 啟動入口（scripts）
│     ├─ next.config.* / nuxt.config.*
│     └─ (lockfile)
│
├─ .venv/
├─ specs/
│  └─ requirements.md
├─ requirements.txt
├─ run_app.bat
├─ .env
└─ .env.example
```

### 啟動進入點

* **Node SSR**：`src/web/package.json` 的 `scripts.dev` / `scripts.start`
* （如果你用自訂 server）才會有明確檔案型 entry：`src/web/server/index.ts`

### Port 資訊維護在哪

* **維護位置**：根目錄 `.env`
* **只需要前端（SSR server）port**：`FRONTEND_PORT`
* 若 SSR 內部還要打外部 API，仍用 `API_BASE_URL`

---

## B5. 前端非 SPA（Node SSR） + 後端 Python（API）同 repo
> 適合維持單一 repo，但前端仍使用 Next/Nuxt 等 SSR 框架，後端則用 Python API 獨立存在。
### 目錄

```
project-root/
├─ src/
│  ├─ server/
│  │  └─ app/
│  │     ├─ __main__.py
│  │     ├─ main.py
│  │     ├─ api/
│  │     ├─ services/
│  │     ├─ data_models/
│  │     └─ config/
│  └─ web/
│     ├─ app/ or pages/
│     ├─ package.json
│     ├─ tsconfig.json
│     └─ dev_server.ts
├─ .venv/
├─ specs/
│  └─ requirements.md
├─ requirements.txt
├─ run_app.bat
├─ .env
└─ .env.example
```

### 關鍵入口
* **Python API**：`src/server/app/__main__.py`
* **Node SSR**：`src/web/package.json` 的 `scripts.dev` / `scripts.start`

### Port 與 env
* **唯一真相來源**：根目錄 `.env`
* **後端**：`BACKEND_HOST`, `BACKEND_PORT`
* **前端 SSR**：`FRONTEND_HOST`, `FRONTEND_PORT`
* **SSR 呼叫 API**：`API_BASE_URL`

---

## B6. 前端非 SPA（Node SSR） + 後端 Node（API）同 repo
> 適合單一 repo 管理兩個 Node 服務：一個 SSR 前端，一個 API 後端。
### 目錄

```
project-root/
├─ src/
│  ├─ server/
│  │  ├─ api/
│  │  ├─ services/
│  │  ├─ data_models/
│  │  ├─ config/
│  │  ├─ package.json
│  │  ├─ tsconfig.json
│  │  └─ server.ts
│  └─ web/
│     ├─ app/ or pages/
│     ├─ package.json
│     ├─ tsconfig.json
│     └─ dev_server.ts
├─ .venv/
├─ specs/
│  └─ requirements.md
├─ requirements.txt
├─ run_app.bat
├─ .env
└─ .env.example
```

### 關鍵入口
* **Node API**：`src/server/package.json` 的 `scripts.dev` / `scripts.start`
* **Node SSR**：`src/web/package.json` 的 `scripts.dev` / `scripts.start`

### Port 與 env
* **唯一真相來源**：根目錄 `.env`
* **後端**：`BACKEND_HOST`, `BACKEND_PORT`
* **前端 SSR**：`FRONTEND_HOST`, `FRONTEND_PORT`
* **SSR 呼叫 API**：`API_BASE_URL`

---

## C1. 無前端（API-only） + 後端 Python（單體服務）
> 適合純 API、CLI + API、內部 webhook 服務，沒有獨立前端。
### 目錄

```
project-root/
├─ src/
│  └─ app/
│     ├─ __main__.py
│     ├─ main.py
│     ├─ api/
│     ├─ services/
│     ├─ data_models/
│     └─ config/
├─ .venv/
├─ specs/
│  └─ requirements.md
├─ requirements.txt
├─ run_app.bat
├─ .env
└─ .env.example
```

### 關鍵入口
* **Python API**：`src/app/__main__.py`

### Port 與 env
* **唯一真相來源**：根目錄 `.env`
* **後端**：`BACKEND_HOST`, `BACKEND_PORT`
* **沒有 `FRONTEND_*`**

---

## C2. 無前端（API-only） + 後端 Node（單體服務）
> 適合純 Node API/BFF 服務，沒有獨立前端。
### 目錄

```
project-root/
├─ src/
│  └─ app/
│     ├─ api/
│     ├─ services/
│     ├─ data_models/
│     ├─ config/
│     ├─ package.json
│     ├─ tsconfig.json
│     └─ server.ts
├─ .venv/
├─ specs/
│  └─ requirements.md
├─ requirements.txt
├─ run_app.bat
├─ .env
└─ .env.example
```

### 關鍵入口
* **Node API**：`src/app/package.json` 的 `scripts.dev` / `scripts.start`

### Port 與 env
* **唯一真相來源**：根目錄 `.env`
* **後端**：`BACKEND_HOST`, `BACKEND_PORT`
* **沒有 `FRONTEND_*`**

---

# 你要的“完整組合”已全部覆蓋（快速對照你列的條件）

* ✅ 前後端分離：A1 / A2 / A3 / A4
* ✅ monorepo：B1 / B2 / B5 / B6
* ✅ single-service：B3 / B4 / C1 / C2
* ✅ 前端型態：`node_spa`、`node_ssr`、`python_templates`、`none` 都有對應模板
* ✅ 後端型態：`python_api` 與 `node_api` 都有完整對照
* ✅ 啟動進入點：每個組合都有具體 file entry 或 `package.json` scripts entry
* ✅ port / env 規劃：統一根目錄 `.env`，runtime metadata 統一 `.runtime/`
* ✅ 選型流程：先走 `references/usage_scene_decision_tree.md`，再走 `references/apsm_decision_tree.md`，最後用 `project.config.json` 落到模板

如果你希望我再把這些**收斂成一份“公司級規範文件”**（例如：命名規則、env key 固定表、哪些目錄允許新增、哪些不允許），我也可以直接給你定稿版（不用問你一堆問題，直接把規則寫死）。
