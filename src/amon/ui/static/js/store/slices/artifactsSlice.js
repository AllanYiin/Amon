export const initialState = {
  items: [],
  previewItem: null,
};

export function reducer(state = initialState, action = { type: "@@init" }) {
  switch (action.type) {
    case "artifacts/setItems":
      return { ...state, items: Array.isArray(action.payload) ? action.payload : [] };
    case "artifacts/setPreviewItem":
      return { ...state, previewItem: action.payload || null };
    default:
      return state;
  }
}

export const actions = {
  setItems: (payload) => ({ type: "artifacts/setItems", payload }),
  setPreviewItem: (payload) => ({ type: "artifacts/setPreviewItem", payload }),
};

export const selectors = {
  items: (state) => state?.artifacts?.items || [],
  previewItem: (state) => state?.artifacts?.previewItem || null,
};
