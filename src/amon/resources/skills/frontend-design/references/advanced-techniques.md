# Advanced Techniques

## Fluid Typography

Use `clamp()` to build type scales that respond smoothly across viewport sizes.

```css
:root {
  --font-size-sm: clamp(0.875rem, 0.8rem + 0.2vw, 1rem);
  --font-size-base: clamp(1rem, 0.9rem + 0.3vw, 1.125rem);
  --font-size-lg: clamp(1.125rem, 1rem + 0.4vw, 1.25rem);
  --font-size-xl: clamp(1.25rem, 1.1rem + 0.5vw, 1.5rem);
  --font-size-2xl: clamp(1.5rem, 1.3rem + 0.7vw, 2rem);
}
```

## Advanced Color Systems

Use perceptual color spaces such as `oklch` when the browser and stack support them.

```css
:root {
  --primary-base: oklch(60% 0.15 250);
  --primary-subtle: oklch(95% 0.02 250);
  --primary-emphasis: oklch(50% 0.18 250);
}
```

Adjust lightness between light and dark themes before changing chroma or hue.

## Skeleton Loading Patterns

Skeletons should preserve layout stability and communicate hierarchy.

```tsx
const Skeleton = ({ className }: { className?: string }) => (
  <div className={className} aria-hidden="true" />
);
```

Use the same footprint as the final content. Do not let the layout jump after data arrives.

## Advanced Motion

Motion should guide attention, not distract.

- use short durations for micro-interactions
- stagger reveals only when it improves comprehension
- respect `prefers-reduced-motion`
- keep entering, exiting, and transitioning states visually distinct

```css
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
