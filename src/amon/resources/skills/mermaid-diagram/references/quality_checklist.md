# Quality checklist

Use this checklist before packaging or shipping a new version.

## Structure
- [ ] Folder name is kebab-case
- [ ] SKILL.md exists (case-sensitive)
- [ ] YAML frontmatter starts/ends with ---
- [ ] Frontmatter has name + description
- [ ] No < or > in frontmatter
- [ ] No README.md inside skill folder

## Triggering
- [ ] Triggers on obvious queries
- [ ] Triggers on paraphrases
- [ ] Does NOT trigger on unrelated queries

## Functionality
- [ ] Core workflow works end-to-end
- [ ] Errors handled with actionable guidance
- [ ] Output matches required structure

## Maintenance
- [ ] Version bumped in metadata
- [ ] Changes documented (outside the skill folder, e.g., repo release notes)
