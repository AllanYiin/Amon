export const initialState = {
  projectId: null,
  chatId: null,
  contextPanelWidth: 320,
};

export function reducer(state = initialState, action = { type: "@@init" }) {
  switch (action.type) {
    case "context/setProjectId":
      return { ...state, projectId: action.payload || null };
    case "context/setChatId":
      return { ...state, chatId: action.payload || null };
    case "context/setPanelWidth":
      return { ...state, contextPanelWidth: Number(action.payload || 320) };
    default:
      return state;
  }
}

export const actions = {
  setProjectId: (payload) => ({ type: "context/setProjectId", payload }),
  setChatId: (payload) => ({ type: "context/setChatId", payload }),
  setPanelWidth: (payload) => ({ type: "context/setPanelWidth", payload }),
};

export const selectors = {
  projectId: (state) => state?.context?.projectId || null,
  chatId: (state) => state?.context?.chatId || null,
  panelWidth: (state) => Number(state?.context?.contextPanelWidth || 320),
};
