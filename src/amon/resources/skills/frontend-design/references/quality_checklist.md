# Quality checklist

這份 checklist 用來記錄 frontend-design 目前是否符合 `skill-creator-advanced` 的 readiness gate 規範。
本次 audit 以 `quick_validate.py`、`format_check.py`、`audit_skill_references.py` 與 `SKILL.md` 結構掃描為基礎，並保留 skill 專屬檢核項。

## Final gate
- Audit date: 2026-03-24
- Compliance level: 中
- Overall status: PARTIAL
- Automated checks:
  - [x] `quick_validate.py` passed
  - [x] `format_check.py` passed
  - [x] `audit_skill_references.py` passed
- Key observations:
  - 自動檢查全數通過。
  - 本次新增 checklist 並補上基礎 skill-specific 檢核。
- Structural gaps to keep improving:
  - 缺少明確 role 區塊
  - 缺少明確 decision boundary 區塊
  - output contract 不夠明示
  - 缺少 worked examples / examples 區塊

## Format checks
- [x] skill folder 名稱符合 kebab-case
- [x] `SKILL.md` 存在且通過基本 frontmatter 驗證
- [x] `format_check.py` 為 0 errors / 0 warnings
- [x] `SKILL.md` 內提到的本地 `scripts/`、`references/`、`assets/` 路徑都存在
- [x] `references/quality_checklist.md` 已存在且已依本次 audit 更新
- [x] `SKILL.md` 中沒有待清理的 `TODO` / `[TODO]`

## Requirement and policy checks
- [x] `SKILL.md` 有明確 workflow / instructions
- [ ] 有獨立 `role` 區塊或等價角色定義
- [ ] 有獨立 decision boundary 區塊或等價使用邊界
- [ ] 有明確 output contract / output shape 要求
- [x] 有明確 default follow-through policy / ask-first 邊界
- [ ] 有工具或路由使用規則
- [ ] 有 worked examples / examples 支撐輸出品質

## Common error checks
- [x] 沒有失效的本地引用路徑
- [x] frontmatter / 命名 / description 沒有被 validator 擋下
- [x] 結構與文字格式沒有被 linter 擋下
- [ ] readiness gate 所期待的關鍵區塊已完整具備
- [x] checklist 已與新版 readiness gate 結構對齊

## Skill-specific checks
- [ ] 設計 tokens、components、states 與 layout 彼此一致。
- [ ] 若是 workspace / dashboard / editor 類畫面，primary task 沒有被 stacked UI 稀釋。
- [ ] 若是 workspace / dashboard / editor 類畫面，已有 task model、state model、資訊架構表與 visibility plan。
- [ ] task model 已拆成唯一主目標 / 次目標 / 低頻目標 / 罕見目標。
- [ ] state model 已對每個 state 定義進入條件 / 必顯資訊 / 隱藏資訊 / 主 CTA / 離開條件。
- [ ] 首屏沒有超過 2-3 個主要視覺群組，且只有 1 個主 CTA。
- [ ] 首屏至多 1 個主操作區、1 個狀態區、1 個次要摘要。
- [ ] `reference` 與 `exception-handling` 類資訊沒有長期霸佔主舞台。
- [ ] 相同任務流中的說明文字優先內嵌在元件旁，而不是獨立大型說明卡。
- [ ] responsive、loading、empty、error、focus 與 accessibility 狀態都有被覆蓋。
