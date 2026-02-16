export const initialState = {
  locale: "zh-TW",
  shellView: "chat",
  streaming: false,
};

export function reducer(state = initialState, action = { type: "@@init" }) {
  switch (action.type) {
    case "ui/setLocale":
      return { ...state, locale: action.payload || "zh-TW" };
    case "ui/setShellView":
      return { ...state, shellView: action.payload || "chat" };
    case "ui/setStreaming":
      return { ...state, streaming: Boolean(action.payload) };
    default:
      return state;
  }
}

export const actions = {
  setLocale: (payload) => ({ type: "ui/setLocale", payload }),
  setShellView: (payload) => ({ type: "ui/setShellView", payload }),
  setStreaming: (payload) => ({ type: "ui/setStreaming", payload }),
};

export const selectors = {
  locale: (state) => state?.ui?.locale || "zh-TW",
  shellView: (state) => state?.ui?.shellView || "chat",
  streaming: (state) => Boolean(state?.ui?.streaming),
};
