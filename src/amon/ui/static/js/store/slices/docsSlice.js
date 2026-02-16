export const initialState = {
  items: [],
  filteredItems: [],
  selectedPath: null,
  filterQuery: "",
};

export function reducer(state = initialState, action = { type: "@@init" }) {
  switch (action.type) {
    case "docs/setItems":
      return { ...state, items: Array.isArray(action.payload) ? action.payload : [] };
    case "docs/setFilteredItems":
      return { ...state, filteredItems: Array.isArray(action.payload) ? action.payload : [] };
    case "docs/setSelectedPath":
      return { ...state, selectedPath: action.payload || null };
    case "docs/setFilterQuery":
      return { ...state, filterQuery: String(action.payload || "") };
    default:
      return state;
  }
}

export const actions = {
  setItems: (payload) => ({ type: "docs/setItems", payload }),
  setFilteredItems: (payload) => ({ type: "docs/setFilteredItems", payload }),
  setSelectedPath: (payload) => ({ type: "docs/setSelectedPath", payload }),
  setFilterQuery: (payload) => ({ type: "docs/setFilterQuery", payload }),
};

export const selectors = {
  items: (state) => state?.docs?.items || [],
  filteredItems: (state) => state?.docs?.filteredItems || [],
  selectedPath: (state) => state?.docs?.selectedPath || null,
  filterQuery: (state) => state?.docs?.filterQuery || "",
};
