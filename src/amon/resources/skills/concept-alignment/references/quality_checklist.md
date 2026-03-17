# Quality checklist

Use this checklist before packaging or shipping a new version.

## Structure
- [ ] Folder name is kebab-case
- [ ] `SKILL.md` exists and is valid UTF-8
- [ ] YAML frontmatter contains `name` and `description` only in allowed top-level keys
- [ ] No `README.md` inside the skill folder
- [ ] `references/output-template.md` and `references/diagram-selection.md` exist
- [ ] `assets/evals/evals.json` and `assets/evals/regression_gates.json` are valid JSON

## Triggering
- [ ] Triggers on obvious requests like "先做概念對齊" and "先不要執行，先查背景"
- [ ] Triggers on concept-alignment / background-research paraphrases
- [ ] Does NOT trigger on direct execution, file-summary-only, or Mermaid-only requests
- [ ] Does NOT steal tasks that should go to `web-search-strategy`, `long-document-evidence-reader`, or output-generation skills
- [ ] Works for zh-TW, English terms, and mixed-language prompts

## Output contract
- [ ] First heading is exactly `## Concept Alignment`
- [ ] Output then uses exactly these three `###` headings in order:
- [ ] `### [關鍵概念]定義`
- [ ] `### 收集背景知識`
- [ ] `### 重大影響的具體事件`
- [ ] Does not append extra conclusion, action plan, or final deliverable unless the user explicitly asks
- [ ] Does not use canvas

## Research quality
- [ ] Web research is mandatory, not optional
- [ ] Time-sensitive facts are verified with current sources
- [ ] Important claims include source annotations
- [ ] Relative dates are converted into concrete dates when needed
- [ ] Units, currencies, jurisdictions, and date ranges are clarified
- [ ] Facts, inference, and bias/stereotype notes are clearly separated
- [ ] Laws cite the law name, jurisdiction, and article/section when relevant
- [ ] Papers include source and abstract-level summary in the writer's own words

## Visualization
- [ ] Mermaid is only used when it improves clarity
- [ ] Diagram type matches the information shape
- [ ] Diagrams include source annotations beneath the code block
- [ ] Diagram text is short enough to render cleanly and avoids obvious Mermaid breakers

## Scope discipline
- [ ] The skill does not execute the task body
- [ ] It stops after delivering concept alignment
- [ ] It directly corrects false user premises when evidence contradicts them
- [ ] It asks follow-up questions only when ambiguity would materially change the research route
