import { combineReducers, createStore } from "../core/store.js";
import * as runsSlice from "./slices/runsSlice.js";
import * as uiSlice from "./slices/uiSlice.js";
import * as docsSlice from "./slices/docsSlice.js";
import * as artifactsSlice from "./slices/artifactsSlice.js";
import * as billingSlice from "./slices/billingSlice.js";
import * as contextSlice from "./slices/contextSlice.js";

export const reducers = {
  runs: runsSlice.reducer,
  ui: uiSlice.reducer,
  docs: docsSlice.reducer,
  artifacts: artifactsSlice.reducer,
  billing: billingSlice.reducer,
  context: contextSlice.reducer,
};

export const initialState = {
  runs: runsSlice.initialState,
  ui: uiSlice.initialState,
  docs: docsSlice.initialState,
  artifacts: artifactsSlice.initialState,
  billing: billingSlice.initialState,
  context: contextSlice.initialState,
};

export function createAppStore() {
  return createStore({
    initialState,
    reducer: combineReducers(reducers),
  });
}

export const actions = {
  runs: runsSlice.actions,
  ui: uiSlice.actions,
  docs: docsSlice.actions,
  artifacts: artifactsSlice.actions,
  billing: billingSlice.actions,
  context: contextSlice.actions,
};

export const selectors = {
  runs: runsSlice.selectors,
  ui: uiSlice.selectors,
  docs: docsSlice.selectors,
  artifacts: artifactsSlice.selectors,
  billing: billingSlice.selectors,
  context: contextSlice.selectors,
};
