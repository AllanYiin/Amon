export const initialState = {
  summary: null,
  budgets: null,
};

export function reducer(state = initialState, action = { type: "@@init" }) {
  switch (action.type) {
    case "billing/setSummary":
      return { ...state, summary: action.payload || null };
    case "billing/setBudgets":
      return { ...state, budgets: action.payload || null };
    default:
      return state;
  }
}

export const actions = {
  setSummary: (payload) => ({ type: "billing/setSummary", payload }),
  setBudgets: (payload) => ({ type: "billing/setBudgets", payload }),
};

export const selectors = {
  summary: (state) => state?.billing?.summary || null,
  budgets: (state) => state?.billing?.budgets || null,
};
