---
name: frontend-design
description: 當使用者要做網站、Web App 或元件庫的 UI 設計與前端實作時使用。將需求轉成可上線的介面、設計 tokens、響應式與可用性細節，並在多步驟體驗中納入 user journey/user flow 可視化與 Gestalt 感知原則。
version: 2026.3.13
license: MIT
metadata:
  short-description: 前端 UI 設計、視覺系統與可上線實作工作流程
---

# Frontend Design Skill — Systematic & Creative Web Development

**Skill Location**: `{project_path}/skills/frontend-design/`

This skill transforms vague UI style requirements into executable, production-grade frontend code through a systematic design token approach while maintaining creative excellence. It ensures visual consistency, accessibility compliance, and maintainability across all deliverables.

---

## When to Use This Skill (Trigger Patterns)

**MUST apply this skill when:**

- User requests any website, web application, or web component development
- User mentions design styles: "modern", "premium", "minimalist", "dark mode", "SaaS-style"
- Building dashboards, landing pages, admin panels, or any web UI
- User asks to "make it look better" or "improve the design"
- Creating component libraries or design systems
- User specifies frameworks: React, Vue, Svelte, Next.js, Nuxt, etc.
- Converting designs/mockups to code
- User mentions: Tailwind CSS, shadcn/ui, Material-UI, Chakra UI, etc.

**Trigger phrases:**
- "build a website/app/component"
- "create a dashboard/landing page"
- "design a UI for..."
- "make it modern/clean/premium"
- "style this with..."
- "convert this design to code"

**DO NOT use for:**
- Backend API development
- Pure logic/algorithm implementation
- Non-visual code tasks

---

## Skill Architecture

This skill provides:

1. **SKILL.md** (this file): Core methodology and guidelines
2. **scripts/**: 可復現檢查工具
   - `audit_frontend_principles.py` - Journey/flow + Gestalt 代理指標檢查器
3. **examples/css/**: Production-ready CSS examples
   - `tokens.css` - Design token system
   - `components.css` - Reusable component styles
4. **examples/typescript/**: TypeScript implementation examples
   - `design-tokens.ts` - Type-safe token definitions
   - `theme-provider.tsx` - Theme management
   - `sample-components.tsx` - Component examples
5. **templates/**: Quick-start templates
   - `tailwind.config.js` - Tailwind configuration
   - `globals.css` - Global styles template
6. **references/**: 深度技巧與原則
   - `web-design-principles.md`
   - `accessibility-usability.md`
   - `responsive-typography.md`
   - `journey-flow-gestalt.md`
   - `design-guideline-authoring.md`
7. **assets/evals/**: Trigger 與功能測試
   - `evals.json`
   - `regression_gates.json`

---

## Core Principles (Non-Negotiable)

### 1. **Dual-Mode Thinking: System + Creativity**

**Systematic Foundation:**
- Design tokens first, UI components second
- No arbitrary hardcoded values (colors, spacing, shadows, radius)
- Consistent scales for typography, spacing, radius, elevation
- Complete state coverage (default/hover/active/focus/disabled + loading/empty/error)
- Accessibility as a constraint, not an afterthought

**Creative Execution:**
- AVOID generic "AI slop" aesthetics (Inter/Roboto fonts, purple gradients, cookie-cutter layouts)
- Choose BOLD aesthetic direction: brutalist, retro-futuristic, luxury, playful, editorial, etc.
- Make unexpected choices in typography, color, layout, and motion
- Each design should feel unique and intentionally crafted for its context

### 2. **Tokens-First Methodology**

```
Design Tokens → Component Styles → Page Layouts → Interactive States
```

**Never skip token definition.** All visual properties must derive from the token system.

### 3. **Tech Stack Flexibility**

**Default stack (if unspecified):**
- Framework: React + TypeScript
- Styling: Tailwind CSS
- Components: shadcn/ui
- Theme: CSS custom properties (light/dark modes)

**Supported alternatives:**
- Frameworks: Vue, Svelte, Angular, vanilla HTML/CSS
- Styling: CSS Modules, SCSS, Styled Components, Emotion
- Libraries: MUI, Ant Design, Chakra UI, Headless UI

### 4. **Tailwind CSS Best Practices**

**⚠️ CRITICAL: Never use Tailwind via CDN**

**MUST use build-time integration:**
```bash
npm install -D tailwindcss postcss autoprefixer
npx tailwindcss init -p
```

**Why build-time is mandatory:**
- ✅ Enables tree-shaking (2-15KB vs 400KB+ bundle)
- ✅ Full design token customization
- ✅ IDE autocomplete and type safety
- ✅ Integrates with bundlers (Vite, webpack, Next.js)

**CDN only acceptable for:**
- Quick prototypes/demos
- Internal testing

### 5. **Journey / Flow Must Be Externalized for Multi-Step UX**

If the task includes onboarding, checkout, signup, settings wizards, dashboards with cross-page tasks, or any flow with branching/state transitions:

- Produce a `journey map`, `user flow`, or `wireflow` before polishing UI
- Lock to one actor, one scenario, one goal
- Show chronological steps, not a pile of screens
- Capture user action + system status + friction/opportunity per step
- Make current step, completed steps, and next step visible in UI

Do not rely on high-fidelity screens alone to explain task flow.

### 6. **Gestalt Principles Are Delivery Constraints**

Apply these as implementation rules, not theory trivia:

- **Proximity / Common Region**: related controls must share spacing rhythm and container boundaries
- **Similarity**: components with the same role must share token, size, and interaction patterns
- **Figure-Ground**: primary action, active state, and critical messages must separate clearly from the background
- **Continuation**: layout should create an obvious reading path toward the next step or CTA
- **Closure / Common Fate**: review visually; do not fake certainty if automation cannot prove it

### 7. **Reusable UI Requires Guideline Artifacts**

If the task produces reusable components, design systems, or shared patterns, deliver a guideline document alongside code.

Minimum structure:
- `Usage`
- `Layout`
- `Anatomy`
- `States & Spec`
- `Interaction`
- `Content / Asset`

Do not treat guideline writing as optional decoration.

### 8. **Use Impeccable-Style Anti-Pattern Audits**

Borrow the useful idea from `impeccable`: do not only describe principles, also scan for repeatable anti-patterns.

At minimum, review for:
- generic font stacks that collapse into AI-slop aesthetics
- gradient text / glassmorphism used without hierarchy justification
- vague CTA copy (`OK`, `Submit`, `Yes`, `No`)
- vague error copy (`Something went wrong`, `Invalid input`)

If an anti-pattern is intentionally used, document the rationale instead of silently normalizing it.

---

## Implementation Workflow

### Phase 1: Design Analysis & Token Definition

**Step 1: Understand Context**
```
- Purpose: What problem does this solve? Who uses it?
- Aesthetic Direction: Choose ONE bold direction
- Technical Constraints: Framework, performance, accessibility needs
- Differentiation: What makes this memorable?
- Flow Shape: Is this a single-screen task, user flow, wireflow, or end-to-end journey?
- Reuse Scope: Is this a one-off page or a reusable component/pattern that needs guideline docs?
```

**Step 1.5: Externalize the Experience Flow (Required for multi-step UX)**
```
- Select the correct artifact:
  - Journey map for end-to-end, cross-touchpoint experiences
  - User flow for in-product task completion
  - Wireflow when screen skeleton and sequence must be reviewed together
- Fix ONE persona / actor, ONE scenario, ONE goal
- Lay out the sequence in chronological order
- Record per step: user action, system feedback, pain point/opportunity
- If helpful, add thinking/feeling/saying lanes
```

**Step 2: Generate Design Tokens**

Create comprehensive token system (see `examples/css/tokens.css` and `examples/typescript/design-tokens.ts`):

1. **Semantic Color Slots** (light + dark modes):
   ```
   --background, --surface, --surface-subtle
   --text, --text-secondary, --text-muted
   --border, --border-subtle
   --primary, --primary-hover, --primary-active, --primary-foreground
   --secondary, --secondary-hover, --secondary-foreground
   --accent, --success, --warning, --danger
   ```

2. **Typography Scale**:
   ```
   Display: 3.5rem/4rem (56px/64px), weight 700-800
   H1: 2.5rem/3rem (40px/48px), weight 700
   H2: 2rem/2.5rem (32px/40px), weight 600
   H3: 1.5rem/2rem (24px/32px), weight 600
   Body: 1rem/1.5rem (16px/24px), weight 400
   Small: 0.875rem/1.25rem (14px/20px), weight 400
   Caption: 0.75rem/1rem (12px/16px), weight 400
   ```

3. **Spacing Scale** (8px system):
   ```
   0.5 → 4px, 1 → 8px, 2 → 16px, 3 → 24px, 4 → 32px
   5 → 40px, 6 → 48px, 8 → 64px, 12 → 96px, 16 → 128px
   ```

4. **Radius Scale**:
   ```
   xs: 2px (badges, tags)
   sm: 4px (buttons, inputs)
   md: 6px (cards, modals)
   lg: 8px (large cards, panels)
   xl: 12px (hero sections)
   2xl: 16px (special elements)
   full: 9999px (pills, avatars)
   ```

5. **Shadow Scale**:
   ```
   sm: Subtle lift (buttons, inputs)
   md: Card elevation
   lg: Modals, dropdowns
   xl: Large modals, drawers
   ```

6. **Motion Tokens**:
   ```
   Duration: 150ms (micro), 220ms (default), 300ms (complex)
   Easing: ease-out (enter), ease-in (exit), ease-in-out (transition)
   ```

### Phase 2: Component Development

**Step 3: Build Reusable Components**

Follow this structure (see `examples/typescript/sample-components.tsx`):

```typescript
interface ComponentProps {
  variant?: 'primary' | 'secondary' | 'outline' | 'ghost';
  size?: 'sm' | 'md' | 'lg';
  state?: 'default' | 'hover' | 'active' | 'disabled' | 'loading';
}
```

**Required component states:**
- Default, Hover, Active, Focus, Disabled
- Loading (skeleton/spinner)
- Empty state (clear messaging)
- Error state (recovery instructions)

**Required component features:**
- Accessible (ARIA labels, keyboard navigation)
- Responsive (mobile-first)
- Theme-aware (light/dark mode)
- Token-based styling (no hardcoded values)

**Step 3.5: Write the guideline if the UI is reusable**

For component libraries, shared patterns, or any UI another engineer/designer must reuse:

```
- Usage: when to use / not use
- Layout: spacing, density, breakpoints
- Anatomy: required vs optional parts
- States & Spec: sizes, tokens, states, min tap targets
- Interaction: keyboard, motion, recovery paths
- Content / Asset: CTA labels, error copy, icons, imagery
```

### Phase 3: Page Assembly

**Step 4: Compose Pages from Components**

```
- Use established tokens and components only
- Mobile-first responsive design
- Loading states for async content
- Empty states with clear CTAs
- Error states with recovery options
- Keep flow visibility explicit (current location, completed work, next action)
- Translate journey pain points into UI guardrails or copy
- Match labels and navigation to the user's mental model, not internal jargon
```

### Phase 4: Quality Assurance

**Step 5: Self-Review Checklist**

- [ ] All colors from semantic tokens (no random hex/rgb)
- [ ] All spacing from spacing scale
- [ ] All radius from radius scale
- [ ] Shadows justified by hierarchy
- [ ] Clear type hierarchy with comfortable line-height (1.5+)
- [ ] All interactive states implemented and tested
- [ ] Accessibility: WCAG AA contrast, keyboard navigation, ARIA, focus indicators
- [ ] Responsive: works on mobile (375px), tablet (768px), desktop (1024px+)
- [ ] Loading/empty/error states included
- [ ] Multi-step UX includes journey map, user flow, or wireflow
- [ ] Current step, completed state, and next step are visible where applicable
- [ ] Labels and flows match user mental model / real-world language
- [ ] Error prevention and recovery paths are explicit (retry, undo, back, cancel)
- [ ] Gestalt: proximity/common region used for grouping
- [ ] Gestalt: similarity preserved across same-role components
- [ ] Gestalt: figure-ground supports hierarchy and active focus
- [ ] Gestalt: continuation creates a clear reading path
- [ ] Reusable components include guideline sections (Usage/Layout/Anatomy/States/Interaction/Content)
- [ ] No obvious AI-slop / anti-pattern signals (generic fonts, vague CTA/error copy, unjustified gradient text)
- [ ] Code is maintainable: DRY, clear naming, documented

**Step 6: Run the deterministic audit**

```bash
python skills/frontend-design/scripts/audit_frontend_principles.py <workspace>
python skills/frontend-design/scripts/audit_frontend_principles.py <workspace> --format json
python skills/frontend-design/scripts/audit_frontend_principles.py <workspace> --require-guideline-docs
```

Interpretation:
- `FAIL`: a required structure/proxy is missing
- `WARN`: likely needs visual/manual confirmation
- `MANUAL_REVIEW`: Closure, Common Fate, and Praegnanz still need human judgment

---

## Design Direction Templates

### 1. Minimal Premium SaaS (Most Universal)

```
Visual Style: Minimal Premium SaaS
- Generous whitespace (1.5-2x standard padding)
- Near-white background with subtle surface contrast
- Light borders (1px, low-opacity)
- Very subtle elevation (avoid heavy shadows)
- Unified control height: 44-48px
- Medium-large radius: 6-8px
- Gentle hover states (background shift only)
- Clear but not harsh focus rings
- Low-contrast dividers
- Priority: Readability and consistency
```

**Best for:** Enterprise apps, B2B SaaS, productivity tools

### 2. Bold Editorial

```
Visual Style: Bold Editorial
- Strong typographic hierarchy (large display fonts)
- High contrast (black/white or dark/light extremes)
- Generous use of negative space
- Asymmetric layouts with intentional imbalance
- Grid-breaking elements
- Minimal color palette (1-2 accent colors max)
- Sharp, geometric shapes
- Dramatic scale differences
- Priority: Visual impact and memorability
```

**Best for:** Marketing sites, portfolios, content-heavy sites

### 3. Soft & Organic

```
Visual Style: Soft & Organic
- Rounded corners everywhere (12-24px radius)
- Soft shadows and subtle gradients
- Pastel or muted color palette
- Gentle animations (ease-in-out, 300-400ms)
- Curved elements and flowing layouts
- Generous padding (1.5-2x standard)
- Soft, blurred backgrounds
- Priority: Approachability and comfort
```

**Best for:** Consumer apps, wellness, lifestyle brands

### 4. Dark Neon (Restrained)

```
Visual Style: Dark Neon
- Dark background (#0a0a0a to #1a1a1a, NOT pure black)
- High contrast text (#ffffff or #fafafa)
- Accent colors ONLY for CTAs and key states
- Subtle glow on hover (box-shadow with accent color)
- Minimal borders (use subtle outlines)
- Optional: Subtle noise texture
- Restrained use of neon (less is more)
- Priority: Focus and sophisticated edge
```

**Best for:** Developer tools, gaming, tech products

### 5. Playful & Colorful

```
Visual Style: Playful & Colorful
- Vibrant color palette (3-5 colors)
- Rounded corners (8-16px)
- Micro-animations on hover/interaction
- Generous padding and breathing room
- Friendly, geometric illustrations
- Smooth transitions (200-250ms)
- High energy but balanced
- Priority: Delight and engagement
```

**Best for:** Consumer apps, children's products, creative tools

---

## Standard Prompting Workflow

### Master Prompt Template

```
You are a Design Systems Engineer + Senior Frontend UI Developer with expertise in creative design execution.

[TECH STACK]
- Framework: {{FRAMEWORK = React + TypeScript}}
- Styling: {{STYLING = Tailwind CSS}}
- Components: {{UI_LIB = shadcn/ui}}
- Theme: CSS variables (light/dark modes)

[DESIGN SYSTEM RULES - MANDATORY]
1. Layout: 8px spacing system; mobile-first responsive
2. Typography: Clear hierarchy (Display/H1/H2/H3/Body/Small/Caption); line-height 1.5+
3. Colors: Semantic tokens ONLY (no hardcoded values)
4. Shape: Tiered radius system; tap targets ≥ 44px
5. Elevation: Minimal shadows; borders for hierarchy
6. Motion: Subtle transitions (150-220ms); restrained animations
7. Accessibility: WCAG AA; keyboard navigation; ARIA; focus indicators
8. If the experience has multiple steps, deliver a journey map, user flow, or wireflow first
9. Apply Gestalt: proximity/common region, similarity, figure-ground, continuation
10. If the UI is reusable, deliver a guideline doc with Usage/Layout/Anatomy/States/Interaction/Content
11. Avoid anti-patterns: generic font stacks, vague CTA/error copy, unjustified gradient text

[AESTHETIC DIRECTION]
Style: {{STYLE = Minimal Premium SaaS}}
Key Differentiator: {{UNIQUE_FEATURE}}
Target Audience: {{AUDIENCE}}

[INTERACTION STATES - REQUIRED]
✓ Default, Hover, Active, Focus, Disabled
✓ Loading (skeleton), Empty (with messaging), Error (with recovery)

[OUTPUT REQUIREMENTS]
1. Design Tokens (CSS variables + TypeScript types)
2. Component implementations (copy-paste ready)
3. Journey map/user flow/wireflow when the task is multi-step
4. Page layouts with all states
5. NO hardcoded values; reference tokens only
6. Minimal but clear code comments
7. Include guideline docs when components or patterns are reusable
8. Include the audit command: `python skills/frontend-design/scripts/audit_frontend_principles.py <workspace>`
```

### Token Generation Prompt

```
Generate a complete Design Token system including:

1. Semantic color slots (CSS custom properties):
   - Light mode + Dark mode variants
   - Background, surface, text, border, primary, secondary, accent, semantic colors
   - Interactive states for each (hover, active)

2. Typography scale:
   - Display, H1-H6, Body, Small, Caption, Monospace
   - Include: font-size, line-height, font-weight, letter-spacing

3. Spacing scale (8px base):
   - 0.5, 1, 2, 3, 4, 5, 6, 8, 10, 12, 16, 20, 24 (in rem)

4. Radius scale:
   - xs (2px), sm (4px), md (6px), lg (8px), xl (12px), 2xl (16px), full

5. Shadow scale:
   - sm, md, lg, xl (with color and blur values)
   - Usage guidelines for each tier

6. Motion tokens:
   - Duration: fast (150ms), base (220ms), slow (300ms)
   - Easing: ease-out, ease-in, ease-in-out

7. Component density:
   - Button heights: sm (36px), md (44px), lg (48px)
   - Input heights: sm (36px), md (40px)
   - Padding scales

Output format:
- CSS custom properties (globals.css)
- Tailwind config integration
- TypeScript type definitions
- Usage examples for each token category

DO NOT write component code yet.
```

### Component Implementation Prompt

```
Using the established Design Tokens, implement: <{{COMPONENT_NAME}} />

Requirements:
- Props: variant, size, state, className (for composition)
- States: default, hover, focus, active, disabled, loading, error
- Accessibility: keyboard navigation, ARIA labels, focus management
- Responsive: mobile-first, touch-friendly (44px+ tap targets)
- Styling: Use tokens ONLY (no hardcoded values)
- TypeScript: Full type safety with exported interfaces

Include:
1. Component implementation
2. Usage examples (3-5 variants)
3. Loading state example
4. Error state example
5. Accessibility notes

Output: Production-ready, copy-paste code with JSDoc comments.
```

### Page Development Prompt

```
Build page: {{PAGE_NAME}}

Using:
- Established Design Tokens
- Implemented Components
- {{STYLE}} aesthetic direction

Requirements:
- Responsive layout (mobile/tablet/desktop)
- All interaction states (hover/focus/active/disabled)
- Loading skeleton for async content
- Empty state with clear CTA
- Error state with recovery options
- Accessible (keyboard nav, ARIA, WCAG AA)
- No hardcoded styles (components + utility classes only)
- If multi-step: include current step, completed state, next action, and recovery path
- Apply Gestalt grouping and visual path explicitly

Include:
1. Page component with mock data
2. Journey/user flow artifact when applicable
3. Loading state variant
4. Empty state variant
5. Error state variant
6. Responsive behavior notes

Output: Complete, runnable page component.
```

### Review & Optimization Prompt

```
You are a Frontend Code Reviewer specializing in design systems and accessibility.

Review the implementation and check:

1. Token Compliance:
   - Any hardcoded colors, sizes, shadows, radius?
   - All values from established scales?

2. Typography:
   - Clear hierarchy?
   - Comfortable line-height (1.5+)?
   - Appropriate font sizes for each level?

3. Spacing & Layout:
   - Consistent use of spacing scale?
   - Adequate whitespace?
   - No awkward gaps or cramped sections?

4. Interactive States:
   - Hover/focus/active clearly distinct?
   - Disabled state obviously different?
   - Loading/empty/error states implemented?

5. Accessibility:
   - WCAG AA contrast met?
   - Keyboard reachable?
   - ARIA labels complete?
   - Focus indicators visible?
   - Semantic HTML?

6. Responsive Design:
   - Mobile layout functional (375px)?
   - Tablet optimized (768px)?
   - Desktop enhanced (1024px+)?
   - Touch targets ≥ 44px?

7. Maintainability:
   - DRY principles followed?
   - Clear component boundaries?
   - Consistent naming?
   - Adequate comments?

8. Creative Execution:
   - Matches intended aesthetic?
   - Avoids generic patterns?
   - Unique and memorable?

9. Journey / Flow Visualization:
   - If multi-step, is there a journey map, user flow, or wireflow?
   - Does it fix one actor, one scenario, one goal?
   - Are step order, system feedback, and pain points visible?

10. Gestalt Alignment:
   - Proximity/common region: related items grouped clearly?
   - Similarity: same-role controls visually consistent?
   - Figure-ground: hierarchy obvious at a glance?
   - Continuation: eye path leads to the next action?

11. Guideline Delivery:
   - If reusable, does the output include Usage/Layout/Anatomy/States/Interaction/Content?
   - Can a designer and engineer implement the component from this doc without guesswork?

12. Anti-Pattern Scan:
   - Any vague CTA copy such as `OK` / `Submit`?
   - Any vague error copy such as `Something went wrong`?
   - Any generic font stack or decorative styling that weakens hierarchy?

Output:
- Findings (sorted by severity: Critical, High, Medium, Low)
- Specific fixes (code patches)
- Improvement suggestions
```

---

## Common Pitfalls & Solutions

### ❌ Problem: Vague aesthetic descriptions
### ✅ Solution: Force actionable specifications

```
DON'T: "Make it modern and clean"
DO: 
- Whitespace: 1.5x standard padding (24px instead of 16px)
- Typography: Display 56px, H1 40px, Body 16px, line-height 1.6
- Colors: Neutral gray scale (50-900) + single accent color
- Shadows: Maximum 2 shadow tokens (card + modal only)
- Radius: Consistent 6px (buttons/inputs) and 8px (cards)
- Borders: 1px with --border-subtle (#e5e7eb in light mode)
- Transitions: 150ms ease-out only
```

### ❌ Problem: Each component invents its own styles
### ✅ Solution: Enforce token-only rule

```
RULE: Every visual property must map to a token.

Violations:
- ❌ bg-gray-100 (hardcoded Tailwind color)
- ❌ p-[17px] (arbitrary padding not in scale)
- ❌ rounded-[5px] (radius not in scale)
- ❌ shadow-[0_2px_8px_rgba(0,0,0,0.1)] (arbitrary shadow)

Correct:
- ✅ bg-surface (semantic token)
- ✅ p-4 (maps to spacing scale: 16px)
- ✅ rounded-md (maps to radius scale: 6px)
- ✅ shadow-sm (maps to shadow token)
```

### ❌ Problem: Missing interactive states
### ✅ Solution: State coverage checklist

```
For EVERY interactive element, implement:

Visual States:
- [ ] Default (base appearance)
- [ ] Hover (background shift, shadow, scale)
- [ ] Active (pressed state, slightly darker)
- [ ] Focus (visible ring, keyboard accessible)
- [ ] Disabled (reduced opacity, cursor not-allowed)

Data States:
- [ ] Loading (skeleton or spinner with same dimensions)
- [ ] Empty (clear message + CTA)
- [ ] Error (error message + retry option)

Test each state in isolation and in combination.
```

### ❌ Problem: Multi-step UI designed as disconnected screens
### ✅ Solution: Force journey/flow artifact before polish

```
For onboarding, checkout, setup, or task completion flows:

- [ ] Pick map type: journey map, user flow, or wireflow
- [ ] Lock one persona, one scenario, one goal
- [ ] Show steps in chronological order
- [ ] Mark current, completed, error, and alternative paths
- [ ] Note user action + system response + friction for each step

If the flow cannot be explained without narration, the visualization is incomplete.
```

### ❌ Problem: Gestalt principles discussed abstractly but not implemented
### ✅ Solution: Translate perception into code-level constraints

```
Proximity / Common Region:
- Use section/card/fieldset boundaries
- Use spacing tokens consistently

Similarity:
- Use shared variants and semantic tokens for same-role controls

Figure-Ground:
- Maintain background/surface/text/primary hierarchy
- Ensure active states and CTAs pop from the page

Continuation:
- Use stepper/timeline/connectors/numbered sequence
- Place the next action at the end of the visual path
```

### ❌ Problem: Reusable component shipped without guideline docs
### ✅ Solution: Treat guideline writing as part of the implementation

```
For reusable UI, document:

- Usage: when / when not to use
- Layout: spacing, density, breakpoints
- Anatomy: required vs optional parts
- States & Spec: tokens, sizes, states
- Interaction: keyboard, motion, recovery
- Content / Asset: CTA labels, errors, icons

If engineering still has to guess, the guideline is incomplete.
```

### ❌ Problem: Audit checks principles but misses anti-patterns
### ✅ Solution: Run an anti-pattern scan

```
Scan for:

- Generic fonts (Inter/Roboto/system-ui as default aesthetic)
- Gradient text used as decoration
- Vague CTA labels (OK / Submit / Yes / No)
- Vague error copy (Something went wrong / Invalid input)

These are not always wrong, but they require explicit justification.
```

### ❌ Problem: Generic AI aesthetics
### ✅ Solution: Force creative differentiation

```
BANNED PATTERNS (overused in AI-generated UIs):
- ❌ Inter/Roboto/System fonts as primary choice
- ❌ Purple gradients on white backgrounds
- ❌ Card-grid-card-grid layouts only
- ❌ Generic blue (#3b82f6) as primary
- ❌ Default Tailwind color palette with no customization

REQUIRED CREATIVE CHOICES:
- ✅ Select distinctive fonts (Google Fonts, Adobe Fonts, custom)
- ✅ Build custom color palette (not Tailwind defaults)
- ✅ Design unique layouts (asymmetry, overlap, grid-breaking)
- ✅ Add personality: illustrations, icons, textures, patterns
- ✅ Create signature elements (unique buttons, cards, headers)

Ask yourself: "Would someone recognize this as uniquely designed for this purpose?"
```

### ❌ Problem: Accessibility as afterthought
### ✅ Solution: Accessibility as constraint

```
Build accessibility IN, not ON:

Color Contrast:
- Run contrast checker on all text/background pairs
- Minimum WCAG AA: 4.5:1 (normal text), 3:1 (large text)
- Use tools: WebAIM Contrast Checker, Chrome DevTools

Keyboard Navigation:
- Tab order follows visual flow
- All interactive elements keyboard reachable
- Focus indicator always visible (outline or ring)
- Escape closes modals/dropdowns

ARIA & Semantics:
- Use semantic HTML first (<button>, <nav>, <main>)
- Add ARIA only when semantic HTML insufficient
- aria-label for icon-only buttons
- aria-describedby for form errors
- aria-expanded for disclosure widgets

Test with:
- Keyboard only (no mouse)
- Screen reader (NVDA, JAWS, VoiceOver)
- Reduced motion preference (prefers-reduced-motion)
```

---

## Quick Start: Complete Example

```
You are a Design Systems Engineer + Senior Frontend UI Developer.

[STACK]
React + TypeScript + Tailwind CSS + shadcn/ui

[TASK]
Build a Team Dashboard for a project management app.

[AESTHETIC]
Style: Minimal Premium SaaS
Unique Element: Subtle animated background gradient
Audience: Product managers and software teams

[REQUIREMENTS]
1. Components needed:
   - Header with search and user menu
   - Team members grid (name, role, avatar, status)
   - Invite modal (name, email, role selector)
   - Empty state (no team members yet)
   - Loading skeleton

2. Features:
   - Search/filter team members
   - Click to view member details
   - Invite button opens modal
   - Sort by name/role/status

3. States:
   - Loading (skeleton grid)
   - Empty (with invite CTA)
   - Populated (member cards)
   - Error (failed to load)

[OUTPUT]
1. Design Tokens (globals.css + tailwind.config.ts)
2. Component implementations:
   - TeamMemberCard
   - InviteModal
   - SearchBar
   - UserMenu
3. TeamDashboard page component
4. All states (loading/empty/error)
5. Full TypeScript types
6. Accessibility notes

Rules:
- Mobile-first responsive
- No hardcoded values (use tokens)
- WCAG AA compliance
- Include hover/focus/active states
- Add subtle micro-interactions
```

---

## Examples & Templates

This skill includes production-ready examples in `examples/`:

### CSS Examples (`examples/css/`)

**`tokens.css`** — Complete design token system
- Semantic color tokens (light + dark modes)
- Typography scale with fluid sizing
- Spacing, radius, shadow, motion scales
- CSS custom properties ready to use

**`components.css`** — Component style library
- Buttons (variants, sizes, states)
- Inputs, textareas, selects
- Cards, modals, tooltips
- Navigation, headers, footers
- Loading skeletons
- All with state variants (hover/focus/active/disabled)

**`utilities.css`** — Utility class library
- Layout utilities (flex, grid, container)
- Spacing utilities (margin, padding)
- Typography utilities (sizes, weights, line-heights)
- State utilities (hover, focus, group variants)

### TypeScript Examples (`examples/typescript/`)

**`design-tokens.ts`** — Type-safe token definitions
- Token interfaces and types
- Design system configuration
- Theme type definitions
- Token validators

**`theme-provider.tsx`** — Theme management system
- Theme context provider
- Dark mode toggle
- System preference detection
- Theme persistence (localStorage)

**`sample-components.tsx`** — Production component examples
- Button component (all variants)
- Input component (with validation)
- Card component (with loading states)
- Modal component (with focus management)
- All with full TypeScript types and accessibility

### Templates (`templates/`)

**`tailwind-config.js`** — Optimized Tailwind configuration
- Custom color palette
- Typography plugin setup
- Spacing and sizing scales
- Plugin configurations

**`globals.css`** — Global styles template
- CSS reset/normalize
- Token definitions
- Base element styles
- Utility classes

---

## Output Quality Standards

Every deliverable must meet:

### Code Quality
- ✅ Production-ready (copy-paste deployable)
- ✅ TypeScript with full type safety
- ✅ ESLint/Prettier compliant
- ✅ No hardcoded magic numbers
- ✅ DRY (Don't Repeat Yourself)
- ✅ Clear, descriptive naming
- ✅ JSDoc comments for complex logic

### Design Quality
- ✅ Unique, memorable aesthetic
- ✅ Consistent token usage
- ✅ Cohesive visual language
- ✅ Thoughtful micro-interactions
- ✅ Polished details (shadows, transitions, spacing)

### Accessibility Quality
- ✅ WCAG AA minimum (AAA preferred)
- ✅ Keyboard navigable
- ✅ Screen reader friendly
- ✅ Focus management
- ✅ Semantic HTML
- ✅ ARIA when necessary

### Performance Quality
- ✅ Optimized bundle size (tree-shaking)
- ✅ Lazy loading for heavy components
- ✅ CSS-only animations when possible
- ✅ Minimal re-renders (React memo/useMemo)
- ✅ Responsive images (srcset, sizes)

---

## Verification Checklist

Before delivering code, verify:

**Tokens & System:**
- [ ] All colors from semantic tokens (no hex/rgb hardcoded)
- [ ] All spacing from spacing scale (8px system)
- [ ] All radius from radius scale (xs/sm/md/lg/xl/2xl/full)
- [ ] Shadows minimal and justified
- [ ] Typography hierarchy clear (Display/H1/H2/H3/Body/Small/Caption)
- [ ] Line-height comfortable (1.5+ for body text)

**States & Interactions:**
- [ ] Default state implemented
- [ ] Hover state (visual feedback)
- [ ] Active state (pressed appearance)
- [ ] Focus state (keyboard ring visible)
- [ ] Disabled state (reduced opacity, no pointer)
- [ ] Loading state (skeleton or spinner)
- [ ] Empty state (clear message + CTA)
- [ ] Error state (message + recovery)

**Accessibility:**
- [ ] WCAG AA contrast (4.5:1 text, 3:1 large text)
- [ ] Keyboard navigation complete
- [ ] Focus indicators always visible
- [ ] Semantic HTML used
- [ ] ARIA labels where needed
- [ ] Form labels associated
- [ ] Alt text on images

**Responsive Design:**
- [ ] Mobile layout (375px+) functional
- [ ] Tablet layout (768px+) optimized
- [ ] Desktop layout (1024px+) enhanced
- [ ] Touch targets ≥ 44px
- [ ] Text readable on all sizes
- [ ] No horizontal scroll

**Journey / Flow & Perception:**
- [ ] Multi-step work includes a journey map, user flow, or wireflow
- [ ] One actor, one scenario, one goal are explicit
- [ ] Current step / completed / next action are visible
- [ ] Labels and information architecture match user mental model
- [ ] Error prevention and recovery paths are documented
- [ ] Proximity/common region used to group related items
- [ ] Similarity maintained for same-role components
- [ ] Figure-ground hierarchy is obvious
- [ ] Continuation leads the eye toward the next action
- [ ] Audit script executed and reviewed

**Guideline & Anti-Patterns:**
- [ ] Reusable components include Usage/Layout/Anatomy/States/Interaction/Content docs
- [ ] CTA copy is task-specific, not generic
- [ ] Error copy explains cause and next step
- [ ] Decorative effects are justified and do not reduce readability
- [ ] Generic font stacks are not used by default aesthetic choice

**Creative Execution:**
- [ ] Unique aesthetic (not generic)
- [ ] Matches stated design direction
- [ ] Memorable visual element
- [ ] Cohesive design language
- [ ] Polished details

**Code Quality:**
- [ ] TypeScript types complete
- [ ] No linter errors
- [ ] DRY principles followed
- [ ] Clear component boundaries
- [ ] Consistent naming conventions
- [ ] Adequate comments
- [ ] Production-ready (can deploy as-is)

---

## Advanced Techniques

### 1. Fluid Typography

```css
/* Responsive type scale using clamp() */
:root {
  --font-size-sm: clamp(0.875rem, 0.8rem + 0.2vw, 1rem);
  --font-size-base: clamp(1rem, 0.9rem + 0.3vw, 1.125rem);
  --font-size-lg: clamp(1.125rem, 1rem + 0.4vw, 1.25rem);
  --font-size-xl: clamp(1.25rem, 1.1rem + 0.5vw, 1.5rem);
  --font-size-2xl: clamp(1.5rem, 1.3rem + 0.7vw, 2rem);
  --font-size-3xl: clamp(1.875rem, 1.5rem + 1vw, 2.5rem);
  --font-size-4xl: clamp(2.25rem, 1.8rem + 1.5vw, 3.5rem);
}
```

### 2. Advanced Color Systems

```css
/* Color with opacity variants using oklch */
:root {
  --primary-base: oklch(60% 0.15 250);
  --primary-subtle: oklch(95% 0.02 250);
  --primary-muted: oklch(85% 0.05 250);
  --primary-emphasis: oklch(50% 0.18 250);
  --primary-foreground: oklch(98% 0.01 250);
}

/* Dark mode: adjust lightness only */
[data-theme="dark"] {
  --primary-base: oklch(70% 0.15 250);
  --primary-subtle: oklch(20% 0.02 250);
  --primary-muted: oklch(30% 0.05 250);
  --primary-emphasis: oklch(80% 0.18 250);
  --primary-foreground: oklch(10% 0.01 250);
}
```

### 3. Skeleton Loading Patterns

```tsx
// Animated skeleton with shimmer effect
const Skeleton = ({ className }: { className?: string }) => (
  <div
    className={cn(
      "animate-pulse rounded-md bg-surface-subtle",
      "relative overflow-hidden",
      "before:absolute before:inset-0",
      "before:-translate-x-full before:animate-shimmer",
      "before:bg-gradient-to-r before:from-transparent before:via-white/10 before:to-transparent",
      className
    )}
  />
);

// Usage in components
<Card>
  <Skeleton className="h-4 w-3/4 mb-2" />
  <Skeleton className="h-4 w-1/2 mb-4" />
  <Skeleton className="h-32 w-full" />
</Card>
```

### 4. Advanced Motion

```css
/* Page transitions */
@keyframes fade-in {
  from {
    opacity: 0;
    transform: translateY(8px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

/* Staggered animations */
.stagger-item {
  animation: fade-in 0.3s ease-out backwards;
}
.stagger-item:nth-child(1) { animation-delay: 0ms; }
.stagger-item:nth-child(2) { animation-delay: 50ms; }
.stagger-item:nth-child(3) { animation-delay: 100ms; }
.stagger-item:nth-child(4) { animation-delay: 150ms; }

/* Respect reduced motion */
@media (prefers-reduced-motion: reduce) {
  *,
  *::before,
  *::after {
    animation-duration: 0.01ms !important;
    animation-iteration-count: 1 !important;
    transition-duration: 0.01ms !important;
  }
}
```

---

## Tips for Excellence

1. **Always start with tokens** — Never skip to components
2. **Think mobile-first** — Design for 375px, enhance upward
3. **Validate states early** — Test each interactive state in isolation
4. **Be bold with aesthetics** — Avoid generic patterns
5. **Accessibility is non-negotiable** — Build it in from the start
6. **Use real content** — Test with actual text, images, data
7. **Review your own work** — Self-audit before delivering
8. **Document decisions** — Explain complex styling choices
9. **Keep it maintainable** — Future developers will thank you
10. **Ship production-ready code** — No "TODO" or "FIXME" in deliverables

---

## References & Resources

### Local References（技能內建）
- `references/web-design-principles.md`
- `references/accessibility-usability.md`
- `references/responsive-typography.md`
- `references/journey-flow-gestalt.md`
- `references/design-guideline-authoring.md`

### External Links
- **Tailwind CSS**: https://tailwindcss.com/docs
- **shadcn/ui**: https://ui.shadcn.com
- **A11Y Checklist**: https://www.a11yproject.com/checklist/
- **Nielsen Norman Group – 10 Usability Heuristics**: https://www.nngroup.com/articles/ten-usability-heuristics/
- **NNG – Journey Mapping (PDF)**: https://media.nngroup.com/media/reports/free/Journey_Mapping.pdf
- **NNG – UX Mapping Glossary (PDF)**: https://media.nngroup.com/media/reports/free/UxMappingGlossary.pdf
- **NNG – Interactive UX Maps: A Practice Guide (PDF)**: https://media.nngroup.com/media/reports/free/Interactive_UX_Maps.pdf
- **NNG – Visibility of System Status (PDF)**: https://media.nngroup.com/media/reports/free/VisibilityOfSystemStatus.pdf
- **Interaction Design Foundation – Perception**: https://www.interaction-design.org/literature/topics/perception
- **Interaction Design Foundation – Gestalt Principles**: https://www.interaction-design.org/literature/topics/gestalt-principles
- **pbakaus / impeccable**: https://github.com/pbakaus/impeccable
- **StartCompany – 使用者介面設計**: https://startcompany.tw/%E4%BD%BF%E7%94%A8%E8%80%85%E4%BB%8B%E9%9D%A2%E8%A8%AD%E8%A8%88/
- **Huang Rui-Lin – How to write a UI Design Guideline**: https://huangruilin.tw/2021/09/03/how-to-write-a-uidesign-guideline/
- **Medium – UX 黃金法則：10 大易用性原則**: https://medium.com/@seeuagain/ux-%E9%BB%83%E9%87%91%E6%B3%95%E5%89%87-10-%E5%A4%A7%E6%98%93%E7%94%A8%E6%80%A7%E5%8E%9F%E5%89%87-%E4%BD%A0%E5%81%9A%E5%88%B0%E4%BA%86%E5%B9%BE%E9%A0%85-091c4dcef76d
- **web.dev Responsive Design**: https://web.dev/learn/design/
- **web.dev Typography**: https://web.dev/learn/css/typography/
- **Color Contrast Checker**: https://webaim.org/resources/contrastchecker/
- **Type Scale**: https://typescale.com
- **Modular Scale**: https://www.modularscale.com
- **CSS Custom Properties**: https://developer.mozilla.org/en-US/docs/Web/CSS/Using_CSS_custom_properties

---

**Version**: 3.2.0  
**Last Updated**: March 13, 2026  
**License**: MIT  
**Maintained by**: z-ai platform team
