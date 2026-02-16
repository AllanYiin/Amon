import { createStore as createCoreStore } from "./core/store.js";

export function createStore(initialState = {}) {
  return createCoreStore({ initialState });
}
