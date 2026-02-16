export function qs(selector, root = document) {
  return root.querySelector(selector);
}

export function qsa(selector, root = document) {
  return Array.from(root.querySelectorAll(selector));
}

export function createEl(tagName, attrs = {}, text = "") {
  const element = document.createElement(tagName);
  setAttrs(element, attrs);
  if (text) element.textContent = text;
  return element;
}

export function setText(element, text) {
  if (!element) return;
  element.textContent = text == null ? "" : String(text);
}

export function setAttrs(element, attrs = {}) {
  if (!element) return;
  Object.entries(attrs).forEach(([key, value]) => {
    if (value === undefined || value === null) return;
    element.setAttribute(key, String(value));
  });
}

export function delegate(root, eventName, selector, handler) {
  if (!root || typeof handler !== "function") return () => {};
  const listener = (event) => {
    const target = event.target?.closest?.(selector);
    if (!target || !root.contains(target)) return;
    handler(event, target);
  };
  root.addEventListener(eventName, listener);
  return () => root.removeEventListener(eventName, listener);
}
