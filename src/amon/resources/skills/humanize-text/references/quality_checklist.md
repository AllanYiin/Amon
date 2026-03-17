# Quality checklist

Use this checklist before packaging or shipping a new version.

## Structure
- [ ] Folder name is kebab-case
- [ ] SKILL.md exists
- [ ] YAML frontmatter starts and ends with ---
- [ ] Frontmatter has name and description
- [ ] No README.md inside skill folder

## Triggering
- [ ] Triggers on obvious "humanize / 去 AI 味 / 改自然 / 不要列點" queries
- [ ] Triggers on zh, en, and mixed-language paraphrases
- [ ] Does not trigger on bytes/time/number humanize library requests
- [ ] Does not trigger on detector evasion or cheating requests
- [ ] Does not steal pure translation, research, or spec-writing queries

## Functionality
- [ ] Core workflow preserves meaning and key terms
- [ ] Traditional Chinese guidance is explicit and actionable
- [ ] Output defaults to paragraph prose
- [ ] Output contains no bullet or ordered lists
- [ ] Output does not promise detector bypass
- [ ] Output does not fabricate personal experience

## Maintenance
- [ ] Trigger evals are saved in references/trigger-evals.json
- [ ] Functional evals are saved in assets/evals/evals.json
- [ ] Regression gates are defined in assets/evals/regression_gates.json
- [ ] No-list checker script exists and is documented
