export const initialState = {
  current: null,
  status: "idle",
  list: [],
};

export function reducer(state = initialState, action = { type: "@@init" }) {
  switch (action.type) {
    case "runs/setCurrent":
      return { ...state, current: action.payload || null };
    case "runs/setStatus":
      return { ...state, status: action.payload || "idle" };
    case "runs/setList":
      return { ...state, list: Array.isArray(action.payload) ? action.payload : [] };
    default:
      return state;
  }
}

export const actions = {
  setCurrent: (payload) => ({ type: "runs/setCurrent", payload }),
  setStatus: (payload) => ({ type: "runs/setStatus", payload }),
  setList: (payload) => ({ type: "runs/setList", payload }),
};

export const selectors = {
  current: (state) => state?.runs?.current || null,
  status: (state) => state?.runs?.status || "idle",
  list: (state) => state?.runs?.list || [],
};
