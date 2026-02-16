export function bindTabs(buttons, callback) {
  [...buttons || []].forEach((button) => {
    button.addEventListener("click", () => callback?.(button.dataset.contextTab || button.dataset.route));
  });
}
