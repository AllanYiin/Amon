# Quality checklist

Use this checklist before shipping a new version of this skill.

## Structure
- [ ] Folder name is kebab-case
- [ ] SKILL.md exists and is valid UTF-8
- [ ] YAML frontmatter has `name` and `description`
- [ ] Description clearly says when this skill should trigger
- [ ] No README.md exists inside the skill folder

## Triggering
- [ ] Triggers on "替代解法", "不同思路", "不要只優化原解", "最低摩擦解"
- [ ] Triggers on paraphrases such as "有沒有更簡單作法", "可不可以不用這條路"
- [ ] Does NOT trigger on direct bug-fixing or code-writing requests
- [ ] Does NOT steal work from `spec-organizer`, `frontend-design`, or implementation-oriented skills
- [ ] Handles mixed Chinese and English trigger phrases

## Analysis quality
- [ ] Includes a one-sentence essence reframe
- [ ] Classifies the problem into at least 1 structure model
- [ ] Includes at least 2 cross-domain analogies
- [ ] Identifies relaxable assumptions and new possibilities
- [ ] Splits the current flow into modules and evaluates reorder / replace / remove options
- [ ] Lists mature technologies or non-technical levers with maturity labels

## Solution quality
- [ ] Provides at least 3 genuinely different solution types
- [ ] Each solution includes concept, concrete action, why simpler/stabler, and trade-offs
- [ ] Provides one lowest-friction solution that mainly changes UI or process
- [ ] Corrects wrong user assumptions instead of silently following them
- [ ] Ends with an actionable next experiment or pilot

## Maintenance
- [ ] Evals in `assets/evals/evals.json` reflect realistic prompts
- [ ] Regression gates are defined in `assets/evals/regression_gates.json`
- [ ] Wording stays practical and avoids abstract filler
- [ ] Detailed pattern lists stay in `references/` instead of bloating `SKILL.md`
