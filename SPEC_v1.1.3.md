# 規格整理 v 1.1.3

以下為本地端 Agent 系統 **Amon** 的雙版本規格：

* **版本 B：一般人版（無開發經驗）**：講「能做什麼 / 怎麼做 / 會看到什麼 / 不能做什麼」。
* **版本 A：專業技術版（給工程/架構/QA）**：含模組設計、資料結構、流程、錯誤邏輯、Edge/Abuse cases、API 等。

---

## 一、技術可行性分析（Feasibility）

### 1) 多模型接入（雲端 + 本地）

* **可行**：用「供應商抽象層」統一各家模型；雲端用金鑰連線，本地模型則以「本機端點」或「本機進程」方式接入（例如 OpenAI 相容介面、或本機推理服務）。
* **風險**：不同模型計費/token 計算方式不一致 → 需在「計費/用量記錄」做適配與可設定。

### 2) Skills 生態相容

* **可行且建議直接相容 Claude Skills 檔案結構**：每個 skill 是一個資料夾，入口為 `SKILL.md`，且 `SKILL.md` 由 YAML frontmatter + Markdown 指令組成；skill 可支援自動啟用或手動用 `/skill-name` 觸發。([Claude Code][1])
* **你的要求（檔案結構必須一致）**可以滿足：Amon 只改「放置位置與載入規則」，不改「skill 內部結構」。

### 3) 透過 MCP 呼叫工具（本地/遠端）

* **可行**：MCP 是標準化的「把工具/資料/工作流接到 AI」的協定，能做動態工具列舉與更新。([modelcontextprotocol.io][2])
* 官方 SDK 已涵蓋多語言（含 Python/TypeScript 等）。([modelcontextprotocol.io][3])
* **風險**：工具呼叫帶來安全面（提示注入、路徑/參數注入）→ 必須做權限、白名單、dry-run、trash、審計 log（你也已要求 billing log）。

### 4) Cowork 類型的檔案操作體驗

* Cowork 的核心差異是：使用者授權資料夾後，AI 能直接讀/寫/建立檔案來完成工作（例如整理檔案、產生報告）。([claude.com][4])
* Amon 可在本地用同樣概念實作：**專案工作區授權 + 檔案操作必可回復（trash/版本）+ 操作前預覽與確認**。

---

## 二、版本 B：一般人版規格（無開發經驗）

> 這份規格不談內部技術細節，只談你「怎麼用、能做到什麼、會看到什麼、限制是什麼」。

### 1) Amon 是什麼

Amon 是一個在你電腦上運作的「AI 同事系統」。
你把工作交給它，它會：

* 連接你選的 AI（可以連不同家，也可以連你電腦上的 AI）
* 需要時去使用工具（像是讀檔、整理資料、產生文件）
* 把過程與成果整理成「專案文件」，方便追蹤與交接

### 2) Amon 的家（固定資料夾）

Amon 會把所有東西放在你的家目錄底下：

* `~/.amon/`（Amon 的總資料夾）

  * `projects/`：所有專案都放這裡
  * `skills/`：全域技能（所有專案都能用）
  * `trash/`：回收桶（刪掉的檔案先放這裡，可還原）
  * `logs/`：紀錄檔

    * `billing.log`：**用量/費用紀錄**（獨立一份）
  * `python_env/`：共用工具箱 A（給「資料處理/腳本」用）
  * `node_env/`：共用工具箱 B（給「網頁/自動化工具」用）

> 重點：你不會因為刪錯檔案就完蛋，因為會進回收桶；費用也會被記在 billing.log。

### 3) 你怎麼開始一個專案

你可以：

* 建立新專案（例如「2026Q1 市場研究」）
* 或把現有資料夾變成 Amon 專案（Amon 只在允許的範圍內動檔）

每個專案內都會有：

* 一個「專案設定」
* 一個「專案技能」（只在這個專案生效）
* 一個「文件區」：所有 AI 成員寫的內容都會存成文件，彼此靠文件溝通

### 4) 三種執行模式（Amon 會自動判斷，也可以你指定）

#### A. 單一模式（適合：問答、簡單寫作）

* 你問 → Amon 回答或幫你寫
* 適用：短文、摘要、回信、簡單企劃

#### B. 自我挑剔模式（適合：需要品質、需要多角度）

流程：

1. Amon 先跟你對齊目標、找資料、寫一份初稿
2. Amon 叫出 **10 個不同角度的「評論角色」**（例如：法務、品牌、行銷、技術、老闆視角…）
3. 這 10 個角色各自提出批評與建議（每個人會產生一份「批評文件」）
4. Amon 根據批評補強，輸出完稿

你會看到：

* 初稿文件
* 10 份批評文件
* 最終完稿文件（標註為 Final）

#### C. 專案團隊模式（適合：複雜任務/多交付物）

這是「專案經理帶隊」的做法：

1. **專案經理**把你的需求拆成待辦清單（TODO list）
2. **角色工廠**依照每個待辦需要的專長，生出一組專家成員（分工不重疊）
3. 專家成員「同時」各做各的，並把成果寫成文件
4. **稽核者**檢查每份文件夠不夠格，不合格就退回重做
5. **專案經理**把碎片整合成一份「交付級」成品（不是把段落硬貼起來）
6. （可選）**驗收委員會**做最後挑剔驗收，只要有人不滿意就回去修到好

你會看到：

* 任務清單（每個待辦的狀態：待處理/執行中/審查中/完成/退回）
* 每個待辦的文件產出
* 稽核回饋
* 最終整合報告

### 5) 你可以怎麼設定 Amon（全域 vs 專案）

* **全域設定**：影響所有專案（例如：預設用哪個 AI、每天費用上限、回收桶保留幾天）
* **專案設定**：只影響這個專案（例如：這個專案指定用某個 AI、或指定一定要走團隊模式）

### 6) 限制與保護（非常重要）

* Amon **只能在你允許的專案範圍內**讀/改檔案
* 任何「可能造成損失」的動作（大量搬移/刪除/覆蓋）：

  * 會先給你看「預計變更清單」
  * 刪除會先進回收桶，可還原
* Amon 的輸出會「一段一段即時顯示」，不會等全部寫完才一次跳出

### 7) 主要畫面示意（淺色模式 + 配色）

* 主色：#1E40AF（深藍，用於標題/主按鈕）
* 輔色：#DB2777（粉紅，用於強調/進行中）
* 成功：#10B981（綠）
* 警示：#F59E0B（橘）
* 背景：#F8FAFC（很淡的灰藍）

#### SVG：首頁（專案列表）

```svg
<svg width="900" height="520" viewBox="0 0 900 520" xmlns="http://www.w3.org/2000/svg">
  <rect x="0" y="0" width="900" height="520" fill="#F8FAFC"/>
  <!-- Left sidebar -->
  <rect x="20" y="20" width="200" height="480" rx="14" fill="#FFFFFF" stroke="#E2E8F0"/>
  <text x="40" y="55" font-family="Inter, sans-serif" font-size="16" font-weight="700" fill="#0F172A">Amon</text>
  <rect x="40" y="80" width="160" height="36" rx="10" fill="#1E40AF"/>
  <text x="60" y="104" font-family="Inter, sans-serif" font-size="13" font-weight="700" fill="#FFFFFF">＋ 新增專案</text>
  <text x="40" y="150" font-family="Inter, sans-serif" font-size="11" font-weight="700" fill="#64748B">導覽</text>
  <text x="40" y="175" font-family="Inter, sans-serif" font-size="12" fill="#0F172A">專案</text>
  <text x="40" y="200" font-family="Inter, sans-serif" font-size="12" fill="#0F172A">技能</text>
  <text x="40" y="225" font-family="Inter, sans-serif" font-size="12" fill="#0F172A">回收桶</text>
  <text x="40" y="250" font-family="Inter, sans-serif" font-size="12" fill="#0F172A">用量/費用</text>

  <!-- Main -->
  <rect x="240" y="20" width="640" height="480" rx="14" fill="#FFFFFF" stroke="#E2E8F0"/>
  <text x="265" y="55" font-family="Inter, sans-serif" font-size="16" font-weight="700" fill="#0F172A">專案列表</text>

  <!-- Search -->
  <rect x="265" y="75" width="420" height="36" rx="10" fill="#F1F5F9" stroke="#E2E8F0"/>
  <text x="285" y="98" font-family="Inter, sans-serif" font-size="12" fill="#64748B">搜尋專案…</text>

  <!-- Project cards -->
  <rect x="265" y="130" width="590" height="90" rx="12" fill="#F8FAFC" stroke="#E2E8F0"/>
  <text x="285" y="160" font-family="Inter, sans-serif" font-size="14" font-weight="700" fill="#0F172A">2026Q1 市場研究</text>
  <text x="285" y="185" font-family="Inter, sans-serif" font-size="12" fill="#64748B">最後更新：今天 14:20 ｜ 模式：團隊</text>
  <rect x="730" y="155" width="105" height="34" rx="10" fill="#1E40AF"/>
  <text x="756" y="177" font-family="Inter, sans-serif" font-size="12" font-weight="700" fill="#FFFFFF">開啟</text>

  <rect x="265" y="235" width="590" height="90" rx="12" fill="#FFFFFF" stroke="#E2E8F0"/>
  <text x="285" y="265" font-family="Inter, sans-serif" font-size="14" font-weight="700" fill="#0F172A">產品規格整理</text>
  <text x="285" y="290" font-family="Inter, sans-serif" font-size="12" fill="#64748B">最後更新：昨天 ｜ 模式：自我挑剔</text>
  <rect x="730" y="260" width="105" height="34" rx="10" fill="#1E40AF"/>
  <text x="756" y="282" font-family="Inter, sans-serif" font-size="12" font-weight="700" fill="#FFFFFF">開啟</text>

  <!-- Footer hint -->
  <text x="265" y="475" font-family="Inter, sans-serif" font-size="11" fill="#64748B">
    提示：刪除的檔案會先進回收桶，可還原；用量/費用在「用量/費用」頁查看
  </text>
</svg>
```

#### SVG：專案工作台（聊天 + 任務 + 文件）

```svg
<svg width="900" height="560" viewBox="0 0 900 560" xmlns="http://www.w3.org/2000/svg">
  <rect x="0" y="0" width="900" height="560" fill="#F8FAFC"/>

  <!-- Top bar -->
  <rect x="20" y="20" width="860" height="56" rx="14" fill="#FFFFFF" stroke="#E2E8F0"/>
  <text x="40" y="54" font-family="Inter, sans-serif" font-size="14" font-weight="700" fill="#0F172A">專案：2026Q1 市場研究</text>
  <rect x="720" y="34" width="140" height="28" rx="10" fill="#1E40AF"/>
  <text x="740" y="53" font-family="Inter, sans-serif" font-size="12" font-weight="700" fill="#FFFFFF">切換模式 ▾</text>

  <!-- Left: tasks -->
  <rect x="20" y="90" width="260" height="450" rx="14" fill="#FFFFFF" stroke="#E2E8F0"/>
  <text x="40" y="120" font-family="Inter, sans-serif" font-size="13" font-weight="700" fill="#0F172A">任務清單</text>

  <!-- task items -->
  <rect x="40" y="135" width="220" height="60" rx="12" fill="#F8FAFC" stroke="#E2E8F0"/>
  <circle cx="55" cy="165" r="6" fill="#DB2777"/>
  <text x="70" y="160" font-family="Inter, sans-serif" font-size="12" font-weight="700" fill="#0F172A">競品摘要</text>
  <text x="70" y="182" font-family="Inter, sans-serif" font-size="11" fill="#64748B">狀態：執行中</text>

  <rect x="40" y="205" width="220" height="60" rx="12" fill="#FFFFFF" stroke="#E2E8F0"/>
  <circle cx="55" cy="235" r="6" fill="#F59E0B"/>
  <text x="70" y="230" font-family="Inter, sans-serif" font-size="12" font-weight="700" fill="#0F172A">風險與限制</text>
  <text x="70" y="252" font-family="Inter, sans-serif" font-size="11" fill="#64748B">狀態：審查中</text>

  <!-- Middle: chat -->
  <rect x="300" y="90" width="380" height="450" rx="14" fill="#FFFFFF" stroke="#E2E8F0"/>
  <text x="320" y="120" font-family="Inter, sans-serif" font-size="13" font-weight="700" fill="#0F172A">對話</text>

  <!-- chat bubbles -->
  <rect x="320" y="140" width="320" height="56" rx="14" fill="#F1F5F9"/>
  <text x="335" y="165" font-family="Inter, sans-serif" font-size="11" fill="#0F172A">你：請做 2026Q1 市場研究，整理競品與策略。</text>

  <rect x="340" y="210" width="320" height="78" rx="14" fill="#EEF2FF"/>
  <text x="355" y="235" font-family="Inter, sans-serif" font-size="11" fill="#0F172A">Amon：我會用「團隊模式」拆任務並產出文件。</text>
  <text x="355" y="255" font-family="Inter, sans-serif" font-size="11" fill="#0F172A">接著我會先給你一份待辦清單供確認。</text>

  <!-- input -->
  <rect x="320" y="500" width="270" height="32" rx="10" fill="#F1F5F9" stroke="#E2E8F0"/>
  <text x="335" y="521" font-family="Inter, sans-serif" font-size="11" fill="#64748B">輸入任務…</text>
  <rect x="595" y="500" width="65" height="32" rx="10" fill="#1E40AF"/>
  <text x="612" y="521" font-family="Inter, sans-serif" font-size="11" font-weight="700" fill="#FFFFFF">送出</text>

  <!-- Right: documents -->
  <rect x="700" y="90" width="180" height="450" rx="14" fill="#FFFFFF" stroke="#E2E8F0"/>
  <text x="720" y="120" font-family="Inter, sans-serif" font-size="13" font-weight="700" fill="#0F172A">文件</text>

  <rect x="720" y="140" width="140" height="54" rx="12" fill="#F8FAFC" stroke="#E2E8F0"/>
  <text x="730" y="166" font-family="Inter, sans-serif" font-size="11" font-weight="700" fill="#0F172A">PM_整合報告.md</text>
  <text x="730" y="184" font-family="Inter, sans-serif" font-size="10" fill="#10B981">Final</text>

  <rect x="720" y="204" width="140" height="54" rx="12" fill="#FFFFFF" stroke="#E2E8F0"/>
  <text x="730" y="230" font-family="Inter, sans-serif" font-size="11" font-weight="700" fill="#0F172A">競品摘要_成員A.md</text>

  <rect x="720" y="268" width="140" height="54" rx="12" fill="#FFFFFF" stroke="#E2E8F0"/>
  <text x="730" y="294" font-family="Inter, sans-serif" font-size="11" font-weight="700" fill="#0F172A">稽核回饋.json</text>
</svg>
```

### 8) 我建議你補充的功能（一般人能懂版）

1. **「先預覽再動手」**：Amon 要改/搬/刪檔之前，先列出清單給你按「同意」。
2. **「一鍵回復」**：回收桶可搜尋、可還原到原位置。
3. **「費用上限」**：每天/每專案可設上限，超過就停止並提醒。
4. **「成果一鍵打包」**：把最終報告 + 所有中間文件 + 任務清單打包成一份交付資料夾。
5. **「常用流程模板」**：例如「市場研究」「產品規格」「投影片產生」「會議紀錄整理」一鍵套用。

---

## 三、版本 A：專業技術版規格（給工程/架構/QA）

### 0) 名詞定義

* **Workspace / Project**：Amon 的專案工作區（檔案、任務、文件、紀錄、設定都在這裡）。
* **Skill**：可重用的工作流程/知識包，入口檔為 `SKILL.md`（含 YAML frontmatter + Markdown 指令）。([Claude Code][1])
* **MCP Server**：提供工具/資源/提示模板的外部服務；Amon 以 MCP Client 連上它並呼叫工具。([modelcontextprotocol.io][2])
* **Agent**：具角色設定 + 技能 + 工具權限的執行者（PM / Role Factory / Stem / Auditor / Committee Member …）。
* **Document**：跨 Agent 溝通與交付物的基礎（Markdown/JSON…），落地到專案文件夾中。

---

### 1) 產品目標 / 非目標（Goals / Non-goals）

#### Goals

1. 本地端 Agent 系統 **Amon**，類 Cowork：可在授權範圍內讀寫檔案，產出交付物。([claude.com][4])
2. 支援多模型供應商（API Key）+ 本地模型接入。
3. 支援 MCP 工具呼叫（本地/遠端），可動態發現/更新工具列表。([modelcontextprotocol.info][5])
4. Global/Project 設定可覆寫（配置優先級明確）。
5. 三種執行模式：單一 / 自我批評 / 專案團隊（Teamworks workflow）。
6. 文件導向協作：所有交付與溝通以文件落地，可追蹤、可回放、可審計。
7. 內建 Agent：角色工廠、專案經理、幹細胞 Agent（+ 稽核者建議列為內建）。

#### Non-goals（v1 不做或可延後）

* 分散式叢集調度、K8s 等大型維運體系（遵守「小專案不過度設計」原則）。
* 複雜權限系統（可用簡化授權 + allowlist + 確認機制先滿足需求）。
* 完整的雲端同步（可先做本機專案匯出/匯入）。

---

### 2) 目錄結構（強制）

#### 2.1 Amon 根目錄（固定：`~/.amon`）

```
~/.amon/
  config.yaml                 # Global config
  projects/                   # All projects
  skills/                     # Global skills (Claude skills-compatible structure)
    <skill-name>/
      SKILL.md
      ...supporting files...
  python_env/                 # Shared Python environment (venv)
  node_env/                   # Shared Node.js environment
  trash/                      # Soft-deleted files/projects
  logs/
    amon.log                  # operational log (JSONL recommended)
    billing.log               # billing & token usage log (JSONL)
  cache/
    skills_index.json         # parsed skill metadata cache
    mcp_registry.json         # resolved MCP tool registry cache
```

#### 2.2 每個專案資料夾（`~/.amon/projects/<project_id>`）

> 專案內同時支援「Amon 狀態」與「Claude skills 相容資料夾」。

```
~/.amon/projects/<project_id>/
  amon.project.yaml           # Project config (overrides global)
  workspace/                  # user-visible working files (optional; can be root if preferred)
  docs/                       # cross-agent documents (Markdown/JSON)
  tasks/                      # task definitions and status
    tasks.json
  sessions/                   # chat transcripts, events
    <session_id>.jsonl
  logs/
    project.log               # project-level log
  .claude/
    skills/                   # Project skills (Claude-compatible location)
      <skill-name>/
        SKILL.md
        ...
  .amon/
    state.json                # internal state snapshot (optional)
    locks/                    # prevent concurrent mutation
```

> **Skills 相容性說明**：
> Claude Code/Claude skills 的結構是「`<skill>/SKILL.md` + YAML frontmatter」，並可放在 `~/.claude/skills/...` 或 `.claude/skills/...`。([Claude Code][1])
> Amon：
>
> * Global skills 放 `~/.amon/skills/...`（結構一致）
> * Project skills 放在專案內 `.claude/skills/...`（路徑也對齊 Claude）

---

### 3) 組態設計（Global / Project）

#### 3.1 Config precedence

1. CLI 參數 / 這次任務 prompt 指定（最高）
2. Project config：`~/.amon/projects/<id>/amon.project.yaml`
3. Global config：`~/.amon/config.yaml`
4. 預設值（最低）

#### 3.2 Global config（範例 YAML）

```yaml
amon:
  data_dir: "~/.amon"
  default_mode: "auto"          # auto | single | self_critique | team
  ui:
    theme: "light"
    streaming: true

models:
  default_provider: "openai"
  providers:
    openai:
      api_key_ref: "keyring:openai"
      default_model: "gpt-5"
    anthropic:
      api_key_ref: "keyring:anthropic"
      default_model: "claude-3.5"
    google:
      api_key_ref: "keyring:google"
      default_model: "gemini-2.0"
  local:
    enabled: true
    endpoints:
      - name: "ollama_local"
        type: "openai_compatible"
        base_url: "http://127.0.0.1:11434/v1"
        default_model: "llama3.1"

skills:
  global_dir: "~/.amon/skills"
  project_dir_rel: ".claude/skills"
  auto_load:
    enabled: true
    max_skills_per_turn: 3
    selection: "hybrid"         # keyword | embedding | llm_router | hybrid

tools:
  mcp:
    enabled: true
    servers:
      - name: "filesystem"
        transport: "stdio"
        command: ["node", "/path/to/mcp-filesystem-server.js"]
        allowed: true
      - name: "git"
        transport: "http"
        url: "http://127.0.0.1:9010"
        allowed: false           # default deny, require explicit enable per project
    permissions:
      require_confirm_for:
        - "filesystem.write"
        - "filesystem.delete"
      allowed_paths:
        - "~/.amon/projects"
      deny_globs:
        - "**/.ssh/**"
        - "**/.gnupg/**"

billing:
  enabled: true
  currency: "USD"
  daily_budget: 10.0
  per_project_budget: 5.0
  price_table:
    openai:gpt-5:
      input_per_1m: 0
      output_per_1m: 0
    anthropic:claude-3.5:
      input_per_1m: 0
      output_per_1m: 0
```

> 註：價格表（price_table）在 v1 可先由使用者維護；之後再加「自動更新」也行（但會牽涉網路與一致性）。

---

### 4) 核心工作流與模式

#### 4.1 Mode auto-selection（自動判斷）

Amon 在收到任務後先做「任務分類」：

* 維度：**複雜度（低/中/高）**、**交付物類型（回答/文章/研究/多文件/需要工具操作）**、**風險（需要改檔/刪檔/大量變更）**
* 輸出：建議模式 + 需要的資源（工具、skills、成員數）

**預設規則（v1 可 rule-based + 可選 LLM router）：**

* 低複雜、單一輸出 → single
* 需要「品質提升、多角度校正」但不需要大量工具操作 → self_critique
* 需要「多交付物、拆任務、平行作業、稽核、整合」→ team

#### 4.2 Single Agent mode

* 單 Agent 直接完成
* 可啟用 skills auto-load（最多 N 個 skills 注入上下文）
* Streaming 輸出

#### 4.3 Self-critique mode（你的規格）

**流程：**

1. **Writer Agent**：概念對齊 →（可選）上網/工具收集素材 → 初稿
2. **Role Factory**：產生 10 個與主題相關的人設（review personas）
3. **Critic Agents x10**：各自扮演提出批評（每人輸出一份 `docs/reviews/<persona>.md`）
4. **Writer Agent**：整合批評，產出完稿（`docs/final.md`）

**強制落地文件：**

* `docs/draft.md`
* `docs/reviews/*.md`
* `docs/final.md`（標註 Final）

#### 4.4 Team mode（依附件 Teamworks workflow 微調落地）

參考你提供的協作工作流（Planning → Staffing → Execution → Audit → Synthesis → Consensus），我建議在 Amon 定義為：

1. **Planning（PM）**：拆解任務 → 產出 TODO list（含 requiredCapabilities）
2. **Staffing（Role Factory）**：產生專業成員 personas（分工互補）
3. **Execution（Members = Stem Agents with personas）**：平行執行，每個 task 產出 Markdown 文件
4. **Audit（Auditor）**：逐 task 審查（APPROVED/REJECTED + feedback）
5. **Synthesis（PM）**：整合為交付級報告（避免碎裂拼貼）
6. **Consensus（Committee，可選）**：多位委員全員一致同意制；否則打回優化（可設定委員數、門檻）

> MCP 的工具可在 Execution/Audit/PM 階段使用，且工具列表可動態更新。([modelcontextprotocol.info][5])

---

### 5) 內建 Agents（角色與責任）

#### 5.1 角色工廠（Role Factory）

**責任**：

* 根據 task 列表與 requiredCapabilities 產生 personas
* 原則：技能不重疊；每人 1–2 核心專業；背景描述具體（可追責）

**Persona schema（JSON）**

```json
{
  "id": "p-001",
  "name": "資料分析顧問",
  "role": "Analyst",
  "description": "擅長市場資料拆解與洞察",
  "skills": ["market-research", "data-synthesis"],
  "capabilities": ["research", "summarize", "spreadsheet"]
}
```

#### 5.2 專案經理（Project Manager）

**責任**：

* 任務拆解、分派、追蹤狀態
* 整合交付物（產生 final report）
* 推進稽核/委員會迭代

#### 5.3 幹細胞 Agent（Stem Agent）

**責任**：

* 在拿到 persona 前：只有通用能力（讀寫文件、基本對話）
* 拿到 persona 後：載入 persona + 專案 skills + 允許工具 → 變成專家成員
* 專家成員輸出必落地到 `docs/`（跨 agent 溝通基礎）

#### 5.4 稽核者（Auditor）— 建議列為內建

**責任**：

* 對每個 task 的文件做稽核（輸出 JSON：APPROVED/REJECTED + feedback）
* 可選：針對工具使用與引用來源做檢查

#### 5.5 委員會成員（Committee Members）— 可選

**責任**：

* 高標準驗收；採全員一致同意（unanimous）或可設定門檻

---

### 6) Memory System（已整合）

> 本段目的：**把「記憶模組」正式補進 Amon 的「總規格」中**，讓它不再是外掛，而是
>
> * 任務執行（Graph Runtime）
> * Agent 協作
> * Skills / Tools
> * 檢索與再利用
>
> 的**共同基礎層**。
>
> 以下內容是「**規格補丁（Spec Addendum）**」，已與你前面所有決策完全對齊（Graph-first、文件導向、Tool Maker、Scheduler）。

#### 一、在 Amon 中，Memory 是什麼（正式定義）

##### 1.1 定位（非常重要）

在 Amon 裡：

> **Memory 不是聊天記錄，也不是向量庫而已，而是：
> 「所有任務、文件、Agent 行為、工具輸出，經過結構化與消歧後，可被圖（Graph）與 Agent 再利用的知識層。」**

因此 Memory 必須：

* 可追溯（traceable to source）
* 可結構化（人事時地物）
* 可關聯（Knowledge Graph）
* 可檢索（Hybrid: structure + vector）
* 可被 Graph node 當 input 使用

---

#### 二、Memory 在整體架構中的位置（總覽）

```
┌─────────────┐
│  Graph Run  │  ← single / self_critique / team / schedule
└──────┬──────┘
       │ produces
       ▼
┌─────────────────────┐
│  Artifacts Layer    │  docs / tasks / sessions / tool outputs
└──────┬──────────────┘
       │ ingest
       ▼
┌─────────────────────────────────────────┐
│           Memory Ingestion Pipeline      │
│  chunk → normalize → disambiguate → tag  │
│            → embed → graph-link          │
└──────┬──────────────────────────────────┘
       │ indexed as
       ▼
┌─────────────────────────────────────────┐
│ Memory Store                             │
│ - chunks.jsonl                           │
│ - normalized.jsonl                      │
│ - entities.jsonl                        │
│ - tags.jsonl                            │
│ - triples.jsonl (Knowledge Graph)       │
│ - vector index                          │
└──────┬──────────────────────────────────┘
       │ queried by
       ▼
┌─────────────────────────────────────────┐
│ Agents / Graph Nodes / Tools / Scheduler │
└─────────────────────────────────────────┘
```

👉 **關鍵結論**：

* 每一次 Graph Run **結束後必定觸發 Memory Ingestion**
* Memory 是 **Graph 的副產品 + 下次 Graph 的燃料**

---

#### 三、Memory 落地結構（正式納入總規格）

```
~/.amon/projects/<project_id>/
  memory/
    chunks.jsonl          # 原始切片
    normalized.jsonl      # 日期 / 地點標準化
    entities.jsonl        # 人名 / 組織 / 物件 + 指代消歧
    tags.jsonl            # tags_markdown + embedding_text
    triples.jsonl         # Knowledge Graph (S-P-O)
    index/
      vectors/            # 向量索引（faiss / sqlite / other）
      metadata.db         # 結構化索引（time / geo / entity）
```

> ⚠️ **這是強制結構（MUST）**，不是建議。

---

#### 四、Memory Ingestion Pipeline（正式規格）

每次 Graph Run 結束後，Runtime **必須**執行以下 pipeline（可非同步，但不可略過）：

##### Stage 0：來源蒐集（Extract）

來源包含：

* `sessions/<run_id>.jsonl`
* `docs/**/*.md`
* `tasks/tasks.json`
* 工具輸出（tool stdout artifacts）

切成 **MemoryChunk**（最小可索引單元）

###### MemoryChunk schema

```json
{
  "chunk_id": "c_20260203_0001",
  "project_id": "p001",
  "run_id": "r001",
  "node_id": "n2_draft",
  "source_type": "session|doc|task|tool",
  "source_path": "docs/draft.md",
  "text": "原始內容文字",
  "created_at": "2026-02-03T10:20:30+08:00",
  "lang": "zh-TW"
}
```

---

##### Stage 1：日期標準化（Date Normalization）✅（你指定）

**規則（納入總規格）**

* 所有時間解析必須以：

  * `chunk.created_at`
  * project timezone（default: Asia/Taipei）
* 輸出 ISO-8601
* 保留 raw + confidence

```json
"time": {
  "mentions": [
    {
      "raw": "昨天",
      "resolved_date": "2026-02-02",
      "confidence": 0.78,
      "timezone": "Asia/Taipei"
    }
  ]
}
```

---

##### Stage 2：地理資訊標準化（Geo Normalization）✅

* 同義地名需 canonicalize（台北 / 臺北 / Taipei）
* 每個地點需有 stable `geocode_id`
* 可先用離線字典（v1）

```json
"geo": {
  "mentions": [
    {
      "raw": "台北",
      "normalized": "Taipei City, Taiwan",
      "geocode_id": "geo:tw-tpe",
      "lat": 25.0375,
      "lon": 121.5637,
      "confidence": 0.85
    }
  ]
}
```

---

##### Stage 3：指代消歧（Coreference & Entity Resolution）✅

**納入總規格的安全原則**

* ❌ 不可憑空創造實體
* ❌ 低信心不可強行 resolve
* ✔ 可回溯來源 chunk

```json
{
  "mention": "他",
  "type": "person",
  "resolved_to": "王小明",
  "entity_id": "person:wang_xiaoming",
  "confidence": 0.66
}
```

---

##### Stage 4：人事時地物抽取（NER + Events）

統一類型（MUST）：

* Person
* Organization / Product
* Event
* Object
* Time
* Geo

---

##### Stage 5：**tags_markdown 產生（你要求，正式入規格）**

###### 5.1 產生規則（MUST）

* 來源：`normalized.jsonl + entities.jsonl`
* 固定標頭（不可改）：

  ```md
  ## AMON_MEMORY_TAGS
  ```
* 僅能是「資料描述」
* ❌ 不得包含：

  * system / developer 指令
  * prompt 語言
  * 可執行內容
  * markdown code block

###### 5.2 tags_markdown 範例

```md
## AMON_MEMORY_TAGS
- 人物(Person): 王小明 (entity_id=person:wang_xiaoming)
- 組織/產品(Org/Product): Amon
- 事件(Event): 專案會議 (event_id=event:project_meeting)
- 時間(Time): 2026-02-02 ~ 2026-02-03 (Asia/Taipei)
- 地點(Geo): Taipei City, Taiwan (geo:tw-tpe)
- 來源(Source): docs/draft.md
```

---

##### Stage 6：Embedding Text 組合（正式規範）

> **這是你特別要求、並且寫入總規格的核心規則**

```text
embedding_text =
  <original chunk text>
  + "\n\n"
  + <tags_markdown>
```

###### tags.jsonl schema

```json
{
  "chunk_id": "c_...",
  "tags_markdown": "## AMON_MEMORY_TAGS
- ...",
  "embedding_text": "原文...\n\n## AMON_MEMORY_TAGS\n- ..."
}
```

✅ **驗收條件（寫入 AC）**

* embedding_text 必須同時包含：

  * 原文
  * `## AMON_MEMORY_TAGS` 區塊

---

##### Stage 7：Knowledge Graph 關聯（KG）

###### Triple schema

```json
{
  "subj": "person:wang_xiaoming",
  "pred": "participated_in",
  "obj": "event:project_meeting",
  "chunk_id": "c_..."
}
```

**規則**

* 所有 edge 必須能追溯 chunk_id
* v1 先用 co-occurrence
* 不允許 hallucinated edge

---

#### 五、Memory 與 Graph Runtime 的正式整合點

##### 5.1 Graph Node 可宣告 Memory I/O

```json
{
  "id": "n_research",
  "type": "agent_task",
  "memory": {
    "query": {
      "entities": ["person:wang_xiaoming"],
      "time_range": "last_30_days",
      "top_k": 5
    },
    "inject_as": "context"
  }
}
```

👉 Graph 不是只「寫檔」，而是能「吃記憶」。

---

##### 5.2 Scheduler 與 Memory

* 排程任務可指定：

  * 是否使用歷史 memory
  * 是否只查某時間範圍
* 排程 run 產生的新結果也會再次進入 memory（形成時間序列知識）

---

#### 六、驗收條件（Memory 已納入總 AC）

##### Memory Pipeline

* [ ] 每次 Graph Run 結束必觸發 Memory Ingestion
* [ ] chunks / normalized / entities / tags / triples 都有落地
* [ ] embedding_text 符合「原文 + AMON_MEMORY_TAGS」

##### 檢索

* [ ] 可用 entity + time + vector 查詢
* [ ] 可用 KG 擴展關聯節點

##### 安全

* [ ] tags_markdown 不含任何指令或可執行內容
* [ ] 所有記憶都可 trace 回 source_path + run_id + node_id

---

#### 七、總結（關鍵設計決策已鎖定）

你現在的 Amon 架構，正式確立為：

1. **Graph-first execution**
2. **Document-first collaboration**
3. **Memory as structured knowledge, not raw text**
4. **Embedding = 原文 + 結構化語義標籤**
5. **Knowledge Graph 是一等公民**
6. **Memory 是 Graph 的輸入與輸出**

這個設計已經**超過一般 Agent Framework**，本質上是：

> **一個可重用、可排程、可學習的任務知識引擎**

---

### 7) Hook / Scheduler / Resident Jobs（常駐）

> 本段目的：**把 Hook / 排程 / 任務常駐執行（Resident Jobs）正式納入 Amon「總規格」**，並與既有的 **Graph-first、Chat-as-UI、文件導向、Memory、Tool Maker、安全確認** 完全一致。

#### 一、總規格新增：Hook / Scheduler / Resident Jobs（常駐）

##### 1.1 目標（MUST）

* 自動化（hook、排程、常駐監控）**必須是 deterministic、低成本、可測**，預設**不依賴 LLM**
* 事件觸發、匹配、節流、去重、排程、心跳、重試等**不得使用 LLM**
* 工具執行**直接走 Tool Executor**（MCP 或內建），不得經由 LLM 轉述/判斷
* 只有在「內容理解 / 生成 / 需要語意推論」時才允許使用 LLM（例如：摘要/分類/標籤、整合寫作、推理與解釋）
* 自動化觸發**必須產生 run_id**，交給 Graph Runtime（允許 tool-only graph node）
* 使用者可在 **Chat UI** 以自然語言新增/管理 hook、排程、常駐任務（Router → CommandPlan → Plan Card → confirm）
* 所有觸發與執行全程可追溯：events、runs、logs、billing、artifacts、memory ingestion

##### 1.2 重要原則（MUST）

* **不得繞過安全層**：檔案 allowlist、工具權限、budget 上限、破壞性動作確認（confirm）
* 支援 **常駐** + **可暫停/恢復/停止** + **重啟後可恢復**
* 觸發風暴要可控：dedupe / cooldown / debounce / max_concurrency / backpressure
* **Automation 專用 Budget**：`automation_budget_daily` 預設極低或 0
* automation 觸發的 LLM node 必須 `allow_llm=true`（default false），否則 runtime 拒絕並記錄 `policy.llm_blocked`

##### 1.3 自動化執行路徑（MUST）

Hook / Schedule / Job 觸發後，只能走兩條路：

**A. Tool-only path（優先，零 token）**

* 事件 → Hook matcher（rule）→ 直接 tool call（MCP/內建）→ 落地 artifacts/logs
* 適用：檔案搬移、索引更新、格式轉換、抓取、測試、打包、部署等「可程式化」工作

**B. GraphRun path（可選，視 node type 決定是否用 LLM）**

* 事件 → 產生 graph run → runtime 執行各 node
* Graph node 必須標註 `execution_engine`：
  * `tool`：只可用工具（零 token）
  * `llm`：允許用模型（需受 budget gate）
  * `hybrid`：先 tool 後 llm（需明確標註）

---

#### 二、事件總線（Event Bus）— 全部自動化的共同基礎

##### 2.1 事件落地（MUST）

* 全域事件：`~/.amon/events/events.jsonl`
* 專案事件（可選但建議）：`~/.amon/projects/<id>/.amon/events/events.jsonl`

##### Event schema（JSONL）

```json
{
  "event_id": "e_20260205_000123",
  "ts": "2026-02-05T14:20:30+08:00",
  "scope": "global|project",
  "project_id": "p001",
  "type": "doc.updated",
  "actor": {"kind":"user|agent|system|job","id":"job:jb_watch_docs"},
  "source": {"run_id":"r001","node_id":"n2_draft","path":"docs/draft.md"},
  "payload": {"path":"docs/draft.md","size":10423,"mime":"text/markdown"},
  "risk": "low|medium|high"
}
```

##### 2.2 標準事件類型（v1 MUST）

* Project：`project.created/updated/deleted/restored/opened`
* Run：`run.started/node_started/node_succeeded/node_failed/completed/cancelled`
* Docs/Workspace：`doc.created/updated/deleted`、`workspace.file_added/modified/deleted`
* Tasks：`task.created/updated/completed/rejected`
* Tools：`tool.forged/tested/registered/failed`
* Memory：`memory.ingest_started/ingest_completed/chunk_added/index_updated`
* Billing：`billing.usage_updated/budget_exceeded`

---

#### 三、Hook 系統（Event → Action → GraphRun）

##### 3.1 Hook 定義存放（MUST）

* 全域：`~/.amon/hooks/<hook_id>.yaml`
* 專案：`~/.amon/projects/<id>/hooks/<hook_id>.yaml`

##### 3.2 Hook YAML schema（v1）

```yaml
hook_id: hk_doc_ingest_v1
enabled: true
scope: project
project_id: p001
when:
  event_types: [doc.created, doc.updated]
  filter:
    path_glob: "docs/**/*.md"
    min_size: 200
do:
  action: graph.run
  template_id: tpl_memory_ingest_v1
  vars:
    project_id: "{{event.project_id}}"
    path: "{{event.payload.path}}"
policy:
  require_confirm: false
  cooldown_seconds: 30
  max_concurrency: 1
  dedupe_key: "{{event.type}}:{{event.payload.path}}"
  ignore_actors: ["system"]   # 避免自觸發迴圈
```

##### 3.2.1 Hook action（tool_call）範例（MUST）

```yaml
do:
  action: tool.call
  tool: "filesystem.copy"
  args:
    src: "{{event.payload.path}}"
    dest: "workspace/archive/{{event.payload.basename}}"
policy:
  require_confirm: true
```

##### 3.3 Hook 執行規則（MUST）

* 命中 hook → 先寫事件 `hook.fired`
* 轉成 GraphRun（`graph.run(template_id, vars)`）
* 若 policy/guard 判定高風險或高成本：Run 進入 `PENDING_CONFIRMATION`，等待使用者在 Chat UI 確認

---

#### 四、Scheduler（排程）— 定期產生事件並觸發 GraphRun

##### 4.1 排程存放（MUST）

* `~/.amon/schedules/schedules.json`（或每個 schedule 一檔，v1 可先用 json）

##### 4.2 Schedule schema（v1）

```json
{
  "schedule_id": "sc_daily_brief",
  "enabled": true,
  "timezone": "Asia/Taipei",
  "trigger": {"type":"cron","cron":"0 9 * * *"},
  "job": {
    "action":"graph.run",
    "template_id":"tpl_daily_brief_v1",
    "vars":{"project_id":"p001","language":"zh-TW"}
  },
  "policy": {
    "require_confirm": false,
    "max_concurrency": 1,
    "misfire_grace_seconds": 300,
    "jitter_seconds": 30
  }
}
```

##### 4.3 排程行為（MUST）

* 到點 → 寫 `schedule.fired` 事件 → 觸發 GraphRun
* misfire：在 grace 內補跑一次，否則略過並寫事件 `schedule.misfired`

---

#### 五、Resident Jobs（任務常駐執行）

##### 5.1 Job 定義存放（MUST）

* `~/.amon/jobs/<job_id>.yaml`
* 狀態：`~/.amon/jobs/state/<job_id>.json`

##### 5.2 Job 類型（v1 MUST）

1. `filesystem_watcher`：監控 workspace/docs 變化 → 產生 doc/workspace 事件
2. `polling_job`：每 N 秒輪詢某來源 → 產生自訂事件

##### 5.3 Job YAML schema（v1）

```yaml
job_id: jb_watch_docs
enabled: true
type: filesystem_watcher
scope: project
project_id: p001
config:
  paths: ["~/.amon/projects/p001/docs"]
  recursive: true
  debounce_ms: 800
emit:
  created: doc.created
  modified: doc.updated
  deleted: doc.deleted
policy:
  restart: always
  max_retries: 10
  backoff_seconds: 5
```

##### 5.4 Job Lifecycle（MUST）

狀態：`STOPPED / STARTING / RUNNING / DEGRADED / FAILED / STOPPING`
要求：

* daemon 重啟後可恢復（從 state.json 讀取）
* 出錯依 backoff 重試，超過 max_retries → FAILED 並寫事件 `job.failed`

---

#### 六、Amon Daemon（常駐服務）— 統一承載 hooks/scheduler/jobs

##### 6.1 Daemon 責任（MUST）

* 讀取/寫入 event bus
* 執行 hook matcher
* 執行 scheduler tick
* 執行 resident jobs
* 管理 `PENDING_CONFIRMATION` 的 run queue
* 統一寫 logs 與 billing log（不因 CLI 結束而中斷自動化）

##### 6.2 本機 IPC/API（MUST）

* Chat UI / CLI 都只呼叫本機 API
* daemon 才做真正的長時間運行工作

---

#### 七、與 Graph Runtime 的強制整合

##### 7.1 所有自動化都必須產生 Run（MUST）

* hook/schedule/job 只能「發事件」或「請求 run」
* 真正執行必經 Graph Runtime

##### 7.2 Run metadata 必含 trigger（MUST）

```json
{
  "run_id":"r123",
  "trigger":{"kind":"hook|schedule|job|chat","id":"hk_doc_ingest_v1","event_id":"e_..."},
  "policy":{"allow_llm": false}
}
```

##### 7.3 Graph Node execution_engine（MUST）

```json
{
  "id": "n_index_update",
  "type": "tool_call",
  "execution_engine": "tool",
  "tool": "memory.index_update",
  "args": {"project_id":"{{project_id}}"},
  "outputs": {"doc":"docs/index_update.log"}
}
```

---

#### 八、Chat-as-UI：新增管理命令域（hooks/schedules/jobs）

##### 8.1 支援自然語言（MUST）

* 「新增一個 hook：docs 有更新就跑記憶索引」
* 「每天 9 點跑 daily brief」
* 「常駐監控 docs，有新檔就摘要」

##### 8.2 對應 CommandPlan API（MUST）

* `hooks.list/create/update/enable/disable/delete`
* `schedules.list/add/enable/disable/delete/run_now`
* `jobs.list/start/stop/restart/status/logs`

所有高風險或高成本操作：Plan Card + confirm。

---

#### 九、安全與風險控制（必補）

##### 9.1 無限循環防護（MUST）

* hook 可設定 `ignore_actors`、filter path
* event 必含 actor/source，hook matcher 必可排除 system 觸發

##### 9.2 事件風暴（MUST）

* watcher debounce
* hook dedupe_key + cooldown
* max_concurrency + backpressure（超過上限暫停 job 或丟棄低風險事件）

##### 9.3 Budget gate（MUST）

* hook/schedule/job 觸發的 run 一律受 budget 限制
* 超過上限 → 寫 `billing.budget_exceeded` 並將 run 置為 paused/pending confirmation

---

#### 十、驗收條件（AC）— 納入總 AC

* [ ] 開啟 daemon 後，filesystem watcher 可產生 doc.updated 事件
* [ ] hook 命中後會產生 hook.fired 事件並啟動 graph run
* [ ] schedule cron 會產生 schedule.fired 並啟動 graph run
* [ ] 高風險 action 會進入 PENDING_CONFIRMATION，不會自動執行
* [ ] daemon 重啟後 jobs/schedules/hooks 狀態可恢復
* [ ] 每個 run 都具 trigger metadata，且 events/logs 可追溯

---

### 8) Skills 系統（Claude 相容 + Amon 微調）

#### 7.1 Skill 結構（必須一致）

* 每個 skill 是資料夾
* 入口檔 `SKILL.md` 必存在
* `SKILL.md` 由 YAML frontmatter + Markdown 指令組成；其他支援檔可放在 skill 資料夾內（examples/templates/scripts 等）。([Claude Code][1])

#### 7.2 Skill discovery（索引化 + 按需載入）

* 啟動或開專案時：

  * 掃描 `~/.amon/skills/*/SKILL.md`
  * 掃描 `<project>/.claude/skills/*/SKILL.md`（含子資料夾可選）
  * 解析 frontmatter（name/description/allowed-tools/context…）
  * 建 skill index 到 `~/.amon/cache/skills_index.json`
* 每次對話時：

  * 先用 index 選出候選 skills（最多 N）
  * 只有在需要時才載入完整 `SKILL.md` 內容（節省上下文）
  * 支援 `/skill-name` 手動觸發（Slash command）

#### 7.3 Amon 微調方向（不破壞結構）

* 保留 Claude frontmatter 欄位（至少：name/description/disable-model-invocation/user-invocable/allowed-tools/model/context/agent）。([Claude Code][1])
* 新增 Amon 自有欄位（放在 frontmatter 也可）例如：

  * `amon-risk-level: low|medium|high`（影響是否要二次確認）
  * `amon-default-mode: single|self_critique|team`
  * `amon-artifacts:`（期望輸出的文件清單）

---

### 9) MCP 工具層（Tool Gateway）

#### 8.1 角色

Amon 作為 MCP Client：

* 連接多個 MCP servers（stdio / http / sse / streamable http）
* 動態列出 tools，並可接收 tools 列表變更通知。([modelcontextprotocol.info][5])

#### 8.2 工具權限與安全

**必做：**

* Tool allowlist/denylist（global + project）
* Path allowlist（僅允許專案 workspace 或明確授權路徑）
* 需要破壞性動作時：

  * dry-run（產生「變更計畫」）
  * user confirm（一次性/永久允許）
  * 寫入前自動備份（或至少進 trash）

**強烈建議：**

* 工具輸出當作「不可信輸入」：任何工具返回內容都要經過 prompt-injection 防護（例如：隔離工具輸出、禁止其覆寫 system 指令）。

---

### 10) 文件導向協作（Document-first）

#### 9.1 文件分類

* `docs/draft.md`、`docs/final.md`
* `docs/tasks/<task_id>/*.md`
* `docs/reviews/*.md`
* `docs/audits/<task_id>.json`

#### 9.2 文件格式規範

* Markdown：標題層級清晰；每份文件有固定 frontmatter（可選）
* JSON：稽核輸出固定 schema

**稽核 JSON schema（v1）**

```json
{
  "task_id": "t-001",
  "status": "APPROVED",
  "feedback": "通過理由或修改建議",
  "checked_at": "2026-02-01T12:34:56+08:00"
}
```

---

### 11) Logging 與 Billing（強制）

#### 10.1 log 分流

* `logs/amon.log`：操作/錯誤/工具呼叫/狀態遷移（JSONL）
* `logs/billing.log`：token 用量與成本（JSONL，獨立檔）

#### 10.2 billing.log（JSONL 範例）

```json
{"ts":"2026-02-01T12:00:01+08:00","project_id":"p001","session_id":"s001","agent":"PM","provider":"openai","model":"gpt-5","prompt_tokens":1200,"output_tokens":800,"total_tokens":2000,"cost_usd":0.00}
```

#### 10.3 成本計算策略

* v1：由 config 的 `price_table` 計算（可允許未知價格 → cost 記 0，但 token 一定要記）
* 每日/每專案 budget 超過 → 自動停止高成本模式（例如 team/committee）並提示切換

---

### 12) UI/UX（技術面規格）

#### 11.1 主要頁面

1. Project List（管理/搜尋/建立/刪除/還原）
2. Project Workspace（Chat + Tasks + Documents）
3. Skills Library（global/project skills、啟用狀態、衝突提示）
4. Tools Registry（已連線 MCP servers + tools、權限）
5. Usage & Billing（按 project/session/agent 統計）

#### 11.2 File preview（強制）

任何檔案被「引入」或「即將被改寫」時：

* 顯示預覽（文本前 N 行、圖片縮圖、PDF 頁面縮圖…）
* 預覽縮放必須維持原始寬高比（Aspect Ratio）

#### 11.3 LLM 輸出（強制 Streaming）

* Chat 與文件產生都以 streaming 方式逐段輸出
* 中途可取消（cancel）
* 取消時落地 partial artifacts（標註 incomplete）

---

### 13) API（本機服務介面，便於 UI/CLI 分離）

> v1 建議：Amon Core 提供本機 HTTP API（localhost only），CLI 與 Web UI 都走同一套 API。
> 若你偏好純 CLI，也可先保留 internal API，再逐步補 UI。

#### 12.1 主要 endpoints（示意）

* `POST /v1/projects` 建立專案
* `GET /v1/projects` 列表
* `POST /v1/projects/{id}/sessions` 開啟 session
* `POST /v1/projects/{id}/run` 送出任務（mode=auto/single/self_critique/team）
* `GET /v1/projects/{id}/tasks` 讀取任務清單
* `GET /v1/projects/{id}/docs` 讀取文件列表
* `GET /v1/skills` skills 索引
* `POST /v1/tools/confirm` 確認一次性工具權限
* `GET /v1/billing/summary` 用量摘要

---

### 14) 錯誤處理（Error logic）

#### 13.1 常見錯誤類型

* `CONFIG_INVALID`：設定檔欄位缺失/格式錯
* `MODEL_AUTH_FAILED`：金鑰錯/過期
* `MODEL_RATE_LIMIT`：供應商限流
* `TOOL_DENIED`：工具未授權
* `PATH_NOT_ALLOWED`：檔案路徑不在允許範圍
* `BUDGET_EXCEEDED`：費用超過上限
* `SKILL_PARSE_FAILED`：SKILL.md frontmatter 解析失敗

#### 13.2 失敗回復策略

* 工具改檔前：自動備份/進 trash
* 任務中斷：保留已完成 docs + logs
* Team mode：單一 task 失敗不影響其他 task（但 PM 整合時需標註缺失）

---

### 15) Edge cases / Abuse cases（必補）

1. **提示注入（tool output / file content）**

   * 防護：工具輸出與檔案內容用「資料區塊」隔離；禁止其改寫 system 指令；對工具呼叫加確認與 allowlist。
2. **路徑穿越 / 讀到敏感目錄**

   * 防護：所有路徑 canonicalize + 必須在 allowed_paths 下；拒絕 `..` 與符號連結逃逸。
3. **大量刪改檔案**

   * 防護：批次操作預覽清單 + 二次確認；預設 soft delete 到 trash。
4. **技能衝突（同名 skill）**

   * 規則：Project skill 覆寫 Global skill；UI 必顯示衝突與來源。
5. **計費失真**

   * 策略：token 一律記錄；cost 若無法精準則以 config 價格表估算並標示 `estimated: true`。
6. **Committee 永無止境打回**

   * 防護：max_iterations（預設 2~3），超過就降級為「PM+Auditor」完成並標註限制。

---

### 16) 驗收條件（Acceptance Criteria）

#### A. 專案與持久化

* [ ] 可建立/開啟/關閉專案，重新啟動後可續作（包含 tasks/docs/session logs）
* [ ] 刪除專案會進 `~/.amon/trash`，可還原

#### B. 模型接入

* [ ] 至少支援 2 家雲端供應商 + 1 種本地端點
* [ ] 可在 global / project 設定預設模型
* [ ] 每次呼叫都記錄 token 用量到 `billing.log`

#### C. Skills

* [ ] 能讀 global skills（`~/.amon/skills`）與 project skills（`.claude/skills`）
* [ ] `SKILL.md` YAML frontmatter 可解析，並支援 `/skill-name` 手動觸發
* [ ] Skills 按需載入（index 不等於全文注入）

#### D. MCP 工具

* [ ] 可連至少 1 個 MCP server
* [ ] 可列出 tools；tool 變更可更新 registry（list_changed 或定期 refresh）([modelcontextprotocol.info][5])
* [ ] 破壞性工具呼叫需要確認；路徑不在 allowlist 必拒絕

#### E. 三種模式

* [ ] single：能完成一般問答/寫作並 streaming
* [ ] self_critique：會產生 draft + 10 reviews + final
* [ ] team：能走 Planning→Staffing→Execution→Audit→Synthesis（+ optional consensus）

---

### 17) 測試案例（含 Gherkin/BDD）

```gherkin
Feature: Project persistence

  Scenario: Create project and resume after restart
    Given I create a project named "demo"
    When I start a session and ask Amon to write a short report
    Then Amon should save documents into ~/.amon/projects/<id>/docs
    When I restart Amon and reopen project "demo"
    Then I can see previous session history and documents

Feature: Soft delete and restore

  Scenario: Delete a document goes to trash
    Given a document exists in project docs
    When I delete the document
    Then the document is moved to ~/.amon/trash with a manifest
    And I can restore it back to its original location

Feature: Skills compatibility

  Scenario: Load a Claude-compatible skill
    Given a skill folder contains SKILL.md with YAML frontmatter
    When I invoke "/my-skill argument"
    Then Amon loads SKILL.md content on-demand
    And applies the instructions to generate output

Feature: Self-critique mode

  Scenario: Produce draft, critiques, and final
    Given I run a task in self_critique mode
    When Amon completes execution
    Then docs/draft.md exists
    And docs/reviews contains 10 review files
    And docs/final.md exists and is marked as final

Feature: MCP tool permission

  Scenario: Deny write outside allowed paths
    Given MCP filesystem tool is connected
    And allowed_paths only include ~/.amon/projects
    When an agent tries to write to ~/.ssh/config
    Then the tool call is denied with PATH_NOT_ALLOWED
    And an event is logged in amon.log
```

---

### 18) 我建議你補充的功能（技術版）

1. **變更計畫（Change Plan）機制**：任何會改檔的任務先產出 `docs/change_plan.md`，列出「將修改哪些檔案、每個檔案改什麼」，再執行。
2. **Git 整合（可選）**：專案若是 git repo，改動前自動建立 branch 或 commit，方便回滾。
3. **Skill 安裝/匯入**：支援從資料夾或 zip 匯入 skills（保持結構），並做 frontmatter 檢查。
4. **安全基線**：預設 deny 高風險工具（例如刪檔/網路支付/任意 shell），需 project 層級明確開啟。
5. **品質評測（Evaluation）**：對技能/模式做簡單回歸測試（固定 prompt + 期望輸出格式），避免越改越爛。

---

[1]: https://code.claude.com/docs/en/skills "Extend Claude with skills - Claude Code Docs"
[2]: https://modelcontextprotocol.io/?utm_source=chatgpt.com "What is the Model Context Protocol (MCP)? - Model Context ..."
[3]: https://modelcontextprotocol.io/docs/sdk?utm_source=chatgpt.com "SDKs"
[4]: https://claude.com/blog/cowork-research-preview?utm_source=chatgpt.com "Introducing Cowork"
[5]: https://modelcontextprotocol.info/docs/concepts/tools/?utm_source=chatgpt.com "Tools"

---

## 補充規格（Phase 4）`POST /v1/context/clear`

### Request Body

```json
{
  "scope": "project | chat",
  "project_id": "string",
  "chat_id": "string | null"
}
```

### 語意與限制

- `scope = "project"`
  - 維持既有行為：清除 project-level context（`project_context.md`）。
  - `chat_id` 可省略。
- `scope = "chat"`
  - **必須提供 `chat_id`**。
  - 若缺少 `chat_id`，回傳 `400`，避免誤刪整個 project context。
  - 僅清除對應 `chat_id` 的聊天 session/context，不影響同 project 的其他 chat。

### Response

- `200 OK`

```json
{
  "status": "ok",
  "scope": "project | chat",
  "chat_id": "string | null"
}
```

- `400 Bad Request`
  - scope 非法、缺少 `project_id`、或 `scope=chat` 缺少/非法 `chat_id`。
