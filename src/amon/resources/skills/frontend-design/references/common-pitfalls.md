# Common Pitfalls

## Vague aesthetic descriptions

Problem:
- "Make it modern and clean" is too abstract.

Fix:
- turn aesthetic language into executable specs
- define spacing, type scale, color system, border strength, radius, and motion rules

## Each component invents its own styles

Problem:
- arbitrary Tailwind colors, custom one-off padding, inconsistent radius/shadow

Fix:
- every visual property must map to a token
- reject arbitrary values unless there is a documented exception

## Missing interactive states

Problem:
- only the default state is designed

Fix:
- define default, hover, active, focus, disabled, loading, empty, and error states for every interactive surface

## Multi-step UI designed as disconnected screens

Problem:
- high-fidelity screens exist, but the task flow is unclear

Fix:
- choose journey map, user flow, or wireflow before polish
- lock one persona, one scenario, one goal

## Workbench UI turned into a stacked dashboard

Problem:
- users must scroll through summaries before they reach the real tool

Fix:
- state the single primary task in one sentence
- put the real viewer/editor/compare surface on stage first

## Feature inventory becomes a feature parking lot

Problem:
- the prompt lists many requirements, and the layout answers by giving each one an equal-weight card

Fix:
- classify each item as action-critical, decision-supporting, status-feedback, reference, exception-handling, or audit/history
- merge or defer low-priority items before layout work starts

## Persistent right rail steals attention from the main task

Problem:
- summary cards, rules, or help content permanently occupy the screen even when they are not needed right now

Fix:
- only keep a side panel persistent if it directly changes the user’s next decision
- otherwise move it to drawer, accordion, modal, or secondary tab

## Reference content competes with task execution

Problem:
- instructions, scoring rules, or FAQs appear as large first-class panels next to the main action

Fix:
- embed short helper copy near the control it explains
- move long-form reference to on-demand disclosure

## State-specific UI is rendered all at once

Problem:
- empty, validating, blocked, resolved, and submitted content all coexist, creating thickness without clarity

Fix:
- model the screen states first
- tie visibility to the active state instead of keeping all states present in the same viewport

## Large blank container occupies the main stage

Problem:
- the dominant content region cannot reliably show meaningful content

Fix:
- redesign hierarchy or provide an instructive empty state that explains what is missing, why, and what to do next

## Gestalt principles discussed abstractly but not implemented

Problem:
- the design mentions Gestalt but does not translate it into layout rules

Fix:
- encode grouping, similarity, figure-ground, and reading path into spacing, containers, tokens, and navigation

## Reusable component shipped without guideline docs

Problem:
- code ships, but designers and engineers cannot reuse it safely

Fix:
- include Usage, Layout, Anatomy, States & Spec, Interaction, and Content / Asset sections

## Audit checks principles but misses anti-patterns

Problem:
- reviews look for compliance but miss low-quality defaults

Fix:
- explicitly scan for vague CTA/error copy, generic fonts, unjustified gradient text, and decorative effects without hierarchy value

## Accessibility as afterthought

Problem:
- accessibility is checked late, which causes expensive rework

Fix:
- build keyboard flow, focus rings, semantic HTML, ARIA, contrast, and reduced-motion support into the first implementation pass
