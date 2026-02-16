export function createEventBus() {
  const listeners = new Map();

  function ensure(eventName) {
    if (!listeners.has(eventName)) {
      listeners.set(eventName, new Set());
    }
    return listeners.get(eventName);
  }

  function on(eventName, handler) {
    if (typeof handler !== "function") return () => {};
    const group = ensure(eventName);
    group.add(handler);
    return () => {
      group.delete(handler);
      if (!group.size) listeners.delete(eventName);
    };
  }

  function once(eventName, handler) {
    if (typeof handler !== "function") return () => {};
    const unsubscribe = on(eventName, (payload) => {
      unsubscribe();
      handler(payload);
    });
    return unsubscribe;
  }

  function emit(eventName, payload) {
    const group = listeners.get(eventName);
    if (!group?.size) return;
    group.forEach((handler) => handler(payload));
  }

  return { on, once, emit };
}
