function cloneState(value) {
  if (typeof structuredClone === "function") return structuredClone(value);
  return JSON.parse(JSON.stringify(value));
}

export function combineReducers(sliceReducers = {}) {
  return (state = {}, action = { type: "@@init" }) => {
    const nextState = { ...state };
    Object.entries(sliceReducers).forEach(([key, reducer]) => {
      nextState[key] = reducer(state[key], action);
    });
    return nextState;
  };
}

export function createStore({ initialState = {}, reducer } = {}) {
  let state = cloneState(initialState);
  const listeners = new Set();

  function notify() {
    listeners.forEach((listener) => listener(state));
  }

  function dispatch(action = {}) {
    if (!action || typeof action.type !== "string") {
      throw new Error("store.dispatch(action) requires an action object with string type");
    }

    if (typeof reducer === "function") {
      state = reducer(state, action);
      notify();
      return action;
    }

    if (action.type === "@@store/patch") {
      state = { ...state, ...(action.payload || {}) };
      notify();
      return action;
    }

    return action;
  }

  return {
    getState() {
      return state;
    },
    subscribe(listener) {
      if (typeof listener !== "function") return () => {};
      listeners.add(listener);
      return () => listeners.delete(listener);
    },
    dispatch,
    patch(partial) {
      return dispatch({ type: "@@store/patch", payload: partial });
    },
  };
}
