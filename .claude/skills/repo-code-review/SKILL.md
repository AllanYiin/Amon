---
name: repo-code-review
description: Provide a focused code review checklist for repository changes.
owner: amon
version: 1.0.0
---
# Repo Code Review

1. Summarize the change in 1-3 bullets.
2. Check for security regressions (secrets, path traversal, unsafe defaults).
3. Validate error handling and logging for new paths.
4. Ensure tests and docs are updated.
