export function registerGlobalErrorHandlers() {
  window.addEventListener("error", (event) => {
    console.error("ui_global_error", event.error || event.message);
  });

  window.addEventListener("unhandledrejection", (event) => {
    console.error("ui_unhandled_rejection", event.reason);
  });
}
