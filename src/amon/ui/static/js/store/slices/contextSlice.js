export const initialState = {
  projectId: null,
  threadId: null,
  contextPanelWidth: 320,
};

export function reducer(state = initialState, action = { type: "@@init" }) {
  switch (action.type) {
    case "context/setProjectId":
      return { ...state, projectId: action.payload || null };
    case "context/setThreadId":
      return { ...state, threadId: action.payload || null };
    case "context/setPanelWidth":
      return { ...state, contextPanelWidth: Number(action.payload || 320) };
    default:
      return state;
  }
}

export const actions = {
  setProjectId: (payload) => ({ type: "context/setProjectId", payload }),
  setThreadId: (payload) => ({ type: "context/setThreadId", payload }),
  setPanelWidth: (payload) => ({ type: "context/setPanelWidth", payload }),
};

export const selectors = {
  projectId: (state) => state?.context?.projectId || null,
  threadId: (state) => state?.context?.threadId || null,
  panelWidth: (state) => Number(state?.context?.contextPanelWidth || 320),
};
