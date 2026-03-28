# Implementation Workflow

## Phase 1: Design Analysis and Token Definition

### Step 1: Understand context

Confirm:
- Purpose: what problem this UI solves and for whom
- Primary task: the one job this screen must let the user complete
- Structure contract: which layout constraints are already specified
- Content reliability: which regions can consistently show meaningful content
- Aesthetic direction: choose one bold direction
- Technical constraints: framework, performance, accessibility, design system constraints
- Differentiation: what should make the result memorable
- Flow shape: single-screen task, user flow, wireflow, or end-to-end journey
- Reuse scope: one-off page or reusable component/pattern

### Step 1.5: Externalize the experience flow

Required for multi-step UX.

- Choose the correct artifact:
  - journey map for end-to-end experiences
  - user flow for in-product task completion
  - wireflow when screen skeleton and sequence must be reviewed together
- Fix one persona, one scenario, one goal.
- Lay out the sequence in chronological order.
- Record user action, system feedback, and pain point/opportunity per step.

### Step 1.6: Lock the workbench hierarchy

Required for task-focused tools.

- Name the primary task surface: viewer, diff panel, editor, preview, compare canvas, and so on.
- Reserve the center/main stage for that surface first.
- Move supporting information to sidebars, inspectors, drawers, accordions, or secondary tabs.
- Decide how empty, error, and loading states behave before polishing decoration.
- If the main area cannot reliably render useful content, redesign the hierarchy.

### Step 1.7: Build the information priority and disclosure plan

Required for dashboards, workbenches, reviewers, setup tools, or any screen that mixes primary action, status, and reference content.

- Write the primary job in one sentence. If it cannot fit in one sentence, the screen is not focused enough yet.
- Expand the task model into:
  - primary goal
  - secondary goal
  - low-frequency goal
  - rare goal
- List every intended block, control, and message before drawing layout.
- Tag each item as one of:
  - `action-critical`
  - `decision-supporting`
  - `status-feedback`
  - `reference`
  - `exception-handling`
  - `audit/history`
- Build an information architecture table before layout:
  - item
  - frequency
  - first-viewport required or not
  - task stage / state
  - show condition
  - recommended container
  - collapsible or not
- Map visibility by state such as `empty`, `drafting`, `validating`, `resolved`, `blocked`, `submitted`.
- For each state, define:
  - entry condition
  - user goal
  - must-show content
  - hidden content
  - primary CTA
  - exit condition
- First viewport default:
  - 1 main action surface
  - 1 status surface if the system is actively processing
  - at most 1 supporting summary
- Move `reference` to accordion, drawer, modal, or secondary tab by default.
- Only show `exception-handling` when the relevant failure or edge state is active.
- If a persistent right rail cannot directly help the current task, convert it to contextual disclosure.
- If more than 2-3 primary visual groups remain, merge, defer, or split the flow before styling.

### Step 2: Generate design tokens

Create a complete token system. See `examples/css/tokens.css` and `examples/typescript/design-tokens.ts`.

Required categories:
- Semantic color slots for light and dark mode
- Typography scale
- Spacing scale
- Radius scale
- Shadow scale
- Motion tokens

Recommended baseline:

```text
Colors: background, surface, text, border, primary, secondary, accent, semantic feedback
Typography: Display, H1, H2, H3, Body, Small, Caption
Spacing: 8px system
Radius: xs, sm, md, lg, xl, 2xl, full
Motion: 150ms, 220ms, 300ms + sensible easing
```

## Phase 2: Component Development

### Step 3: Build reusable components

Every interactive component should define:
- variants
- sizes
- states
- accessibility support
- responsive behavior
- theme-aware styling
- token-based styling only

Required states:
- Default
- Hover
- Active
- Focus
- Disabled
- Loading
- Empty
- Error

### Step 3.5: Write the guideline if the UI is reusable

For component libraries, shared patterns, or any UI another engineer/designer must reuse, document:
- Usage
- Layout
- Anatomy
- States & Spec
- Interaction
- Content / Asset

## Phase 3: Page Assembly

### Step 4: Compose pages from components

- Use established tokens and components only.
- Design mobile-first.
- Keep one clear primary task per screen or main view.
- Reserve the main stage for the primary task surface, not summaries about the task.
- Move supporting metadata and low-frequency controls to secondary layers.
- Keep the first viewport focused on work, not explanation panels or card farms.
- Prefer inline helper text near the control that needs it over isolated explanation cards.
- If multiple blocks compete equally, revisit the task model instead of adding more visual chrome.
- Include loading, empty, and error states.
- Keep flow visibility explicit: current location, completed work, next action.
- Match labels and navigation to the user's mental model, not internal jargon.
- Prefer tabs or view switching when users focus on one workspace mode at a time.

## Phase 4: Quality Assurance

### Step 5: Self-review checklist

Check at minimum:
- all colors come from semantic tokens
- spacing and radius use shared scales
- type hierarchy and line-height are coherent
- all interaction states exist
- accessibility covers WCAG AA, keyboard navigation, ARIA, and focus indicators
- responsive behavior works on mobile, tablet, and desktop
- loading/empty/error states exist
- the layout preserves the primary task hierarchy
- a task model, state model, information architecture table, and visibility plan exist when the page is a workbench or workflow screen
- the task model is split into primary / secondary / low-frequency / rare goals
- each information block has an explicit role such as action-critical, status-feedback, or reference
- each state defines entry condition, must-show content, hidden content, and primary CTA
- reference and exception content are conditionally revealed instead of permanently occupying the main stage
- the first viewport has no more than 2-3 primary visual groups
- multi-step UX includes journey map, user flow, or wireflow
- reusable components include guideline docs
- obvious AI-slop anti-patterns are absent or justified

### Step 6: Run the deterministic audit

```bash
python skills/frontend-design/scripts/audit_frontend_principles.py <workspace>
python skills/frontend-design/scripts/audit_frontend_principles.py <workspace> --format json
python skills/frontend-design/scripts/audit_frontend_principles.py <workspace> --require-guideline-docs
```

Interpretation:
- `FAIL`: a required structure or proxy is missing
- `WARN`: likely needs visual or manual confirmation
- `MANUAL_REVIEW`: Closure, Common Fate, or similar perception-heavy checks still need human review
