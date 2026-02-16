export function createHashRouter({ routes, defaultRoute = "chat", onRoute }) {
  const hasRoute = (route) => Object.prototype.hasOwnProperty.call(routes, route);

  function parse(hashValue = window.location.hash) {
    const key = (hashValue || "").replace(/^#\/?/, "").trim().toLowerCase().split("/")[0];
    return hasRoute(key) ? key : defaultRoute;
  }

  function navigate(routeKey) {
    const normalized = hasRoute(routeKey) ? routeKey : defaultRoute;
    window.location.hash = `#/${normalized}`;
  }

  async function sync(hashValue) {
    const current = parse(hashValue);
    if (typeof onRoute === "function") {
      await onRoute(current, routes[current]);
    }
    return current;
  }

  return { parse, navigate, sync };
}
