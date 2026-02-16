export function createStore(initialState = {}) {
  const listeners = new Set();
  const state = { ...initialState };

  return {
    getState() {
      return state;
    },
    patch(partial) {
      Object.assign(state, partial || {});
      listeners.forEach((listener) => listener(state));
    },
    subscribe(listener) {
      listeners.add(listener);
      return () => listeners.delete(listener);
    },
  };
}
