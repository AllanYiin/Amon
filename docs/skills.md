# Skills

本文件說明技能（Skill）格式、索引機制、以及 CLI 使用方式。

## Skill 檔案格式

技能是一個資料夾，必須包含 `SKILL.md`。支援 YAML frontmatter：

```markdown
---
name: 需求摘要
description: 將需求整理成條列摘要
---

# 需求摘要技能

請依照以下格式輸出：
1. 需求重點
2. 風險與假設
3. 後續問題
```

- `name`：技能名稱（預設為資料夾名稱）。
- `description`：簡述技能用途。

## 技能掃描與索引

技能來源：

- 全域技能：`~/.amon/skills`
- 專案技能：`<project>/.claude/skills`

掃描並更新索引：

```bash
amon skills scan
amon skills scan --project <project_id>
```

列出與查看技能：

```bash
amon skills list
amon skills show <name>
```

## 在執行任務時使用技能

CLI 的 `run` 指令可透過 `--skill` 指定多個技能：

```bash
amon run --skill 需求摘要 --skill 測試策略 "請整理專案需求"
```

當指定的技能不存在時，系統會忽略該技能並繼續執行。

## 範例

可參考 `examples/skills/example-skill` 內的完整範例。
