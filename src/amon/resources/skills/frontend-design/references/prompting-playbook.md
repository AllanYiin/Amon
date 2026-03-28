# Prompting Playbook

## Master Prompt Template

```text
You are a Design Systems Engineer + Senior Frontend UI Developer.

[TECH STACK]
- Framework: {{FRAMEWORK}}
- Styling: {{STYLING}}
- Components: {{UI_LIB}}
- Theme: CSS variables or project-native theming

[DESIGN SYSTEM RULES]
1. Layout uses a shared spacing system
2. Typography hierarchy is explicit
3. Colors come from semantic tokens only
4. Shapes and shadows use shared scales
5. Motion is restrained and meaningful
6. Accessibility is mandatory
7. If multi-step, produce a journey map, user flow, or wireflow first
8. If reusable, deliver guideline docs
9. Scan for anti-patterns before final output
10. Before layout, produce a task model, state model, information architecture table, and visibility plan
11. Avoid dashboard/card farm/stacked sections layout unless the task truly is multi-monitoring
12. Keep reference and exception content off the main stage by default

[AESTHETIC DIRECTION]
Style: {{STYLE}}
Key differentiator: {{UNIQUE_FEATURE}}
Target audience: {{AUDIENCE}}

[INTERACTION STATES]
Default, Hover, Active, Focus, Disabled, Loading, Empty, Error

[OUTPUT REQUIREMENTS]
1. Design tokens
2. Component implementations
3. Journey/user-flow artifact when applicable
4. Task model + state model + information architecture table + visibility plan when the screen is a workflow/workbench
5. Page layouts with all states
6. Token-only styling
7. Minimal useful comments
8. Guideline docs when reusable
9. Audit command
```

## Token Generation Prompt

Use when the token system does not exist yet.

Ask for:
- semantic color slots in light/dark mode
- typography scale
- spacing scale
- radius scale
- shadow scale
- motion tokens
- CSS variables, Tailwind integration, and TypeScript types

Do not ask for component code in the same step unless the task is trivial.

## Component Implementation Prompt

Use when tokens already exist and the task is to implement a component.

Require:
- props for variants, sizes, and composition
- default/hover/focus/active/disabled/loading/error states
- accessibility and keyboard support
- responsive behavior
- token-only styling
- usage examples

## Page Development Prompt

Use when components and tokens already exist and the task is to assemble a page.

Require:
- responsive layout
- loading/empty/error states
- explicit primary task hierarchy
- task model split into primary / secondary / low-frequency / rare goals
- state model with entry conditions, must-show content, hidden content, and primary CTA
- information architecture table before layout
- information-role labels for major blocks
- progressive disclosure rules for reference / exception content
- multi-step visibility when applicable
- Gestalt-informed grouping and reading path

## Review Prompt

Use for self-audit or review.

Check:
- token compliance
- type hierarchy
- spacing/layout consistency
- interactive states
- accessibility
- responsive behavior
- maintainability
- creative differentiation
- flow visibility
- task-first information architecture
- progressive disclosure discipline
- guideline delivery
- anti-pattern scan

## Quick-Start Example

Use a structured brief such as:

```text
Build a team dashboard for a project management app.

Stack: React + TypeScript + Tailwind CSS + shadcn/ui
Style: Minimal Premium SaaS
Audience: product managers and software teams

Components:
- header with search and user menu
- team members grid
- invite modal
- empty state
- loading skeleton

Output:
- design tokens
- component implementations
- dashboard page
- all states
- accessibility notes
```

Rule: do not compress token design, flow design, component design, and final review into one vague prompt if the task is non-trivial.
