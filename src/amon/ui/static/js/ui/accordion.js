export function toggleAccordionItem(root, itemId) {
  if (!root) return;
  root.querySelectorAll("[data-accordion-item]").forEach((node) => {
    const shouldOpen = node.dataset.accordionItem === itemId;
    node.classList.toggle("is-open", shouldOpen);
  });
}
