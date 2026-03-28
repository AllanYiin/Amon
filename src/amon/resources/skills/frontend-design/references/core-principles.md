# Core Principles

## 1. Dual-Mode Thinking: System + Creativity

### Systematic foundation
- Design tokens first, UI components second.
- No arbitrary hardcoded values for colors, spacing, shadows, or radius.
- Use consistent scales for typography, spacing, radius, and elevation.
- Cover complete state sets: default, hover, active, focus, disabled, loading, empty, error.
- Treat accessibility as a constraint, not an afterthought.

### Creative execution
- Avoid generic AI-slop aesthetics such as default Inter/Roboto stacks, purple gradients on white, or cookie-cutter card grids.
- Choose one clear visual direction: brutalist, retro-futuristic, luxury, playful, editorial, or another intentional theme.
- Make typography, color, layout, and motion feel crafted for the task instead of interchangeable.

## 2. Tokens-First Methodology

Always work in this order:

```text
Design Tokens -> Component Styles -> Page Layouts -> Interactive States
```

Never skip token definition. All visual properties should derive from the token system.

## 3. Tech Stack Flexibility

### Default stack
- Framework: React + TypeScript
- Styling: Tailwind CSS
- Components: shadcn/ui
- Theme: CSS custom properties with light/dark mode support

### Supported alternatives
- Frameworks: Vue, Svelte, Angular, vanilla HTML/CSS
- Styling: CSS Modules, SCSS, Styled Components, Emotion
- Libraries: MUI, Ant Design, Chakra UI, Headless UI

Choose the stack that matches the repo or user constraints. Do not force a new stack if the project already has one.

## 4. Tailwind CSS Best Practices

Never use Tailwind via CDN for real delivery.

### Required build-time integration

```bash
npm install -D tailwindcss postcss autoprefixer
npx tailwindcss init -p
```

### Why build-time is mandatory
- Enables tree-shaking.
- Supports full token customization.
- Gives IDE autocomplete and safer maintenance.
- Integrates correctly with bundlers such as Vite, webpack, and Next.js.

### CDN is only acceptable for
- Quick prototypes
- Internal demos
- Disposable experiments

## 5. Journey / Flow Must Be Externalized for Multi-Step UX

If the task includes onboarding, checkout, signup, settings wizards, dashboards with cross-page tasks, or any flow with branching/state transitions:

- Produce a `journey map`, `user flow`, or `wireflow` before polishing UI.
- Lock to one actor, one scenario, one goal.
- Show chronological steps, not a pile of disconnected screens.
- Capture user action, system status, and friction/opportunity per step.
- Make current step, completed steps, and next step visible in the UI.

High-fidelity screens alone are not enough to explain flow.

## 6. Gestalt Principles Are Delivery Constraints

Apply these as implementation rules, not theory trivia.

- Proximity / Common Region: related controls must share spacing rhythm and container boundaries.
- Similarity: components with the same role must share tokens, size, and interaction patterns.
- Figure-Ground: primary action, active state, and critical messages must separate clearly from the background.
- Continuation: layout should create an obvious reading path toward the next step or CTA.
- Closure / Common Fate: review visually; if automation cannot prove it, mark for manual review instead of pretending certainty.

## 7. Task-Focused Workbenches Must Preserve the Primary Job

For dashboards, review tools, document viewers, editors, compare screens, or any workspace where users mainly operate one central surface:

- Define the single `primary task` before drawing the layout.
- Let the primary task own the largest, most central, first-scanned region.
- Push metadata, environment info, help copy, and secondary controls into sidebars, drawers, tabs, or collapsible layers.
- Do not turn a workbench into a stacked landing page of summary cards before the real tool.
- If the structure spec already says `top action bar + left navigation + central viewer`, preserve that contract.
- A dominant main-stage container that cannot show value should be redesigned, not decorated.
- Empty states must explain what is missing, why, and what the user should do next.
- On mobile, preserve the primary task first instead of shrinking every desktop panel proportionally.

## 8. Reusable UI Requires Guideline Artifacts

If the task produces reusable components, design systems, or shared patterns, deliver a guideline document alongside code.

Minimum structure:
- Usage
- Layout
- Anatomy
- States & Spec
- Interaction
- Content / Asset

If engineering still has to guess, the guideline is incomplete.

## 9. Use Anti-Pattern Audits

Do not only describe principles. Also scan for repeatable anti-patterns.

At minimum, review for:
- generic font stacks that collapse into AI-slop aesthetics
- gradient text or glassmorphism used without hierarchy justification
- vague CTA copy such as `OK`, `Submit`, `Yes`, `No`
- vague error copy such as `Something went wrong`, `Invalid input`

If an anti-pattern is intentionally used, document the rationale instead of silently normalizing it.
