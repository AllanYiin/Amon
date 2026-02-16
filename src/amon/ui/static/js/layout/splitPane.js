export function createSplitPane({ handle, container, onResize, min = 280, max = 520, bodyResizingClass = "is-resizing-context-panel" }) {
  if (!handle || !container || typeof onResize !== "function") {
    return { destroy() {} };
  }

  let dragging = false;

  const clamp = (value) => Math.max(min, Math.min(max, value));

  const onMove = (event) => {
    if (!dragging) return;
    const rect = container.getBoundingClientRect();
    const width = clamp(rect.right - event.clientX);
    onResize(width);
  };

  const onUp = () => {
    if (!dragging) return;
    dragging = false;
    document.body.classList.remove(bodyResizingClass);
  };

  const onDown = (event) => {
    event.preventDefault();
    dragging = true;
    document.body.classList.add(bodyResizingClass);
  };

  handle.addEventListener("mousedown", onDown);
  window.addEventListener("mousemove", onMove);
  window.addEventListener("mouseup", onUp);

  return {
    destroy() {
      handle.removeEventListener("mousedown", onDown);
      window.removeEventListener("mousemove", onMove);
      window.removeEventListener("mouseup", onUp);
      onUp();
    },
  };
}
