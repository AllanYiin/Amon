/**
 * @typedef {Object} ViewContext
 * @property {HTMLElement} rootEl - 該 view 的容器元素。
 * @property {Object} store - 全域 store。
 * @property {Object} services - Domain services 集合。
 * @property {{toast?: Object, modal?: Object, tabs?: Object, accordion?: Object}} ui - 可重用 UI 元件。
 * @property {(key: string, vars?: Record<string, string|number>) => string} t - i18n 翻譯函式。
 * @property {EventTarget} bus - 事件匯流排。
 */

/**
 * @typedef {Object} ViewContract
 * @property {string} id - View 識別 ID，例如 chat。
 * @property {string} route - 路由路徑，例如 /chat。
 * @property {(ctx: ViewContext) => void} mount - 進入 view 時初始化。
 * @property {() => void} unmount - 離開 view 時清理。
 * @property {(params: Record<string, string>, ctx: ViewContext) => (void|Promise<void>)} [onRoute] - 路由切換到 view 時觸發。
 */

export {};
