# Quality Checklist

## Output Quality Standards

### Code quality
- production-ready and copy-paste deployable
- consistent naming
- minimal duplication
- no hardcoded magic numbers when tokens should exist
- TypeScript types where the stack supports them

### Design quality
- clear and distinctive aesthetic direction
- consistent token usage
- coherent visual language
- meaningful micro-interactions
- polished spacing, shadows, and transitions

### Accessibility quality
- WCAG AA minimum
- keyboard navigable
- semantic HTML first
- ARIA only where needed
- focus management and visible indicators

### Performance quality
- reasonable bundle size
- lazy loading when appropriate
- CSS-first motion when possible
- responsive images and asset discipline

## Verification Checklist

### Tokens and system
- all colors from semantic tokens
- spacing from a shared scale
- radius from a shared scale
- shadows justified by hierarchy
- clear type hierarchy
- comfortable body line-height

### States and interactions
- default state
- hover state
- active state
- focus state
- disabled state
- loading state
- empty state
- error state

### Accessibility
- WCAG AA contrast
- complete keyboard navigation
- visible focus indicators
- semantic HTML
- ARIA labels where needed
- labels and alt text are correct

### Responsive design
- mobile layout works
- tablet layout works
- desktop layout works
- touch targets are large enough
- no accidental horizontal scroll

### Flow and perception
- multi-step work includes journey map, user flow, or wireflow
- one actor, one scenario, one goal are explicit
- current step / completed / next action are visible
- the current screen has one explicit primary task
- a task model exists for workbench/workflow screens
- a state model exists for workbench/workflow screens
- the task model is split into primary / secondary / low-frequency / rare goals
- each information block has an explicit role such as action-critical, status-feedback, or reference
- an information architecture table exists before layout
- each state defines entry condition, must-show content, hidden content, and primary CTA
- the primary task occupies the main stage
- reference content is on-demand unless it directly affects the current decision
- exception-handling content is conditional instead of permanently visible
- supporting information is demoted unless essential
- the first viewport lets users start the real work
- the first viewport contains no more than 2-3 primary visual groups
- only one primary CTA competes for attention at a time
- empty states explain what is missing, why, and what to do next
- labels match the user mental model
- recovery paths are documented
- grouping, similarity, figure-ground, and reading path are visible

### Guideline and anti-patterns
- reusable components include guideline docs
- CTA copy is task-specific
- error copy explains cause and next step
- decorative effects are justified
- default generic font stacks are not the unexamined choice

### Code review
- type definitions complete where applicable
- no linter errors
- clear component boundaries
- consistent naming
- comments only where useful
- production-ready output

## Tips for Excellence

1. Start with tokens.
2. Think mobile-first.
3. Validate states early.
4. Be bold with aesthetics, but disciplined with systems.
5. Treat accessibility as non-negotiable.
6. Test with real content, not placeholders only.
7. Self-audit before delivery.
8. Document non-obvious design decisions.
9. Keep the result maintainable for the next engineer.
