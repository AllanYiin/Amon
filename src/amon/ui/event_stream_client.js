(function (globalScope, factory) {
  if (typeof module === "object" && module.exports) {
    module.exports = factory();
    return;
  }
  globalScope.AmonUIEventStream = factory();
})(typeof globalThis !== "undefined" ? globalThis : window, function () {
  function safeParseJson(raw) {
    if (typeof raw !== "string") return raw || {};
    try {
      return JSON.parse(raw || "{}");
    } catch (_error) {
      return {};
    }
  }

  function createUiEventStore(initialState) {
    const state = {
      run: null,
      jobs: {},
      billing: { total_cost: 0, items: [] },
      docs: [],
      ...initialState,
    };
    const listeners = new Set();

    function notify() {
      listeners.forEach((listener) => listener(state));
    }

    function applyEvent(eventType, payload) {
      if (!eventType) return;
      if (eventType === "run" || eventType === "run.update") {
        state.run = { ...(state.run || {}), ...(payload || {}) };
        notify();
        return;
      }
      if (eventType === "job" || eventType === "job.update") {
        const jobId = payload && payload.job_id ? payload.job_id : "unknown";
        state.jobs[jobId] = { ...(state.jobs[jobId] || {}), ...(payload || {}) };
        notify();
        return;
      }
      if (eventType === "billing" || eventType === "billing.update") {
        const amount = Number(payload && payload.cost);
        if (!Number.isNaN(amount)) {
          state.billing.total_cost += amount;
        }
        state.billing.items.push(payload || {});
        notify();
        return;
      }
      if (eventType === "docs" || eventType === "docs.update") {
        if (Array.isArray(payload && payload.docs)) {
          state.docs = payload.docs.slice();
          notify();
          return;
        }
        if (payload && payload.op === "add" && payload.path) {
          if (!state.docs.includes(payload.path)) {
            state.docs.push(payload.path);
            state.docs.sort();
          }
          notify();
          return;
        }
        if (payload && payload.op === "remove" && payload.path) {
          state.docs = state.docs.filter((item) => item !== payload.path);
          notify();
        }
      }
    }

    return {
      getState() {
        return {
          run: state.run,
          jobs: { ...state.jobs },
          billing: {
            total_cost: state.billing.total_cost,
            items: state.billing.items.slice(),
          },
          docs: state.docs.slice(),
        };
      },
      subscribe(listener) {
        listeners.add(listener);
        return function unsubscribe() {
          listeners.delete(listener);
        };
      },
      applyEvent,
    };
  }

  class EventStreamClient {
    constructor(options) {
      this.options = {
        reconnectBaseMs: 1000,
        reconnectMaxMs: 8000,
        maxReconnectAttempts: Infinity,
        preferSSE: true,
        useMock: false,
        ...options,
      };
      this.lastEventId = null;
      this.reconnectAttempts = 0;
      this.shouldRun = false;
      this.connection = null;
      this.currentTransport = null;
      this.mockController = null;
      this.params = null;
    }

    start(params) {
      this.params = params || {};
      this.shouldRun = true;
      this.reconnectAttempts = 0;
      this._connect();
    }

    stop() {
      this.shouldRun = false;
      this._setStatus("stopped");
      if (this.connection && typeof this.connection.close === "function") {
        this.connection.close();
      }
      this.connection = null;
      if (this.mockController && typeof this.mockController.stop === "function") {
        this.mockController.stop();
      }
      this.mockController = null;
    }

    _connect() {
      if (!this.shouldRun) return;
      if (this.options.useMock) {
        this._connectMock();
        return;
      }
      if (this.options.preferSSE !== false && typeof EventSource !== "undefined") {
        this._connectSSE();
        return;
      }
      if (typeof WebSocket !== "undefined") {
        this._connectWebSocket();
        return;
      }
      if (this.options.mockFactory) {
        this._connectMock();
        return;
      }
      this._setStatus("error", "No stream transport available");
    }

    _connectMock() {
      const factory = this.options.mockFactory || defaultMockFactory;
      this._setStatus("connecting", "mock");
      this.currentTransport = "mock";
      this.mockController = factory({
        emit: (eventType, payload) => this._dispatch(eventType, payload, null),
        close: () => this._scheduleReconnect(),
      });
      this._setStatus("connected", "mock");
    }

    _connectSSE() {
      const url = this._buildSseUrl();
      this.currentTransport = "sse";
      this._setStatus("connecting", "sse");
      const source = new EventSource(url);
      this.connection = source;
      source.onopen = () => {
        this.reconnectAttempts = 0;
        this._setStatus("connected", "sse");
      };
      source.onerror = () => {
        source.close();
        this._scheduleReconnect();
      };
      ["token", "notice", "plan", "result", "run", "job", "billing", "docs", "error", "done"].forEach((eventType) => {
        source.addEventListener(eventType, (event) => {
          const payload = safeParseJson(event.data);
          const eventId = event.lastEventId || null;
          this._dispatch(eventType, payload, eventId);
          if (eventType === "done" || eventType === "error") {
            this.shouldRun = false;
            source.close();
            this.connection = null;
            if (eventType === "error") {
              this._setStatus("error", "stream error event");
            } else {
              this._setStatus("stopped", "stream completed");
            }
          }
        });
      });
    }

    _connectWebSocket() {
      if (!this.options.wsUrlBuilder) {
        this._scheduleReconnect();
        return;
      }
      const ws = new WebSocket(this.options.wsUrlBuilder(this.params || {}, this.lastEventId));
      this.connection = ws;
      this.currentTransport = "websocket";
      this._setStatus("connecting", "websocket");
      ws.onopen = () => {
        this.reconnectAttempts = 0;
        this._setStatus("connected", "websocket");
      };
      ws.onmessage = (event) => {
        const packet = safeParseJson(event.data);
        this._dispatch(packet.event || "message", packet.data || packet, packet.id || null);
      };
      ws.onerror = () => ws.close();
      ws.onclose = () => this._scheduleReconnect();
    }

    _buildSseUrl() {
      const builder = this.options.sseUrlBuilder;
      if (!builder) {
        throw new Error("sseUrlBuilder is required for SSE transport");
      }
      return builder(this.params || {}, this.lastEventId);
    }

    _dispatch(eventType, payload, eventId) {
      if (eventId) {
        this.lastEventId = eventId;
      } else if (payload && typeof payload.last_event_id === "string") {
        this.lastEventId = payload.last_event_id;
      }
      if (typeof this.options.onEvent === "function") {
        this.options.onEvent(eventType, payload || {}, this.lastEventId);
      }
    }

    _scheduleReconnect() {
      if (!this.shouldRun) return;
      if (this.reconnectAttempts >= this.options.maxReconnectAttempts) {
        this._setStatus("error", "reconnect exhausted");
        return;
      }
      this.reconnectAttempts += 1;
      const waitMs = Math.min(
        this.options.reconnectMaxMs,
        this.options.reconnectBaseMs * Math.pow(2, Math.max(this.reconnectAttempts - 1, 0))
      );
      this._setStatus("reconnecting", this.currentTransport);
      const scheduleTimeout = (typeof window !== "undefined" && window.setTimeout) ? window.setTimeout.bind(window) : setTimeout;
      scheduleTimeout(() => this._connect(), waitMs);
    }

    _setStatus(status, detail) {
      if (typeof this.options.onStatusChange === "function") {
        this.options.onStatusChange({ status, detail, transport: this.currentTransport });
      }
    }
  }

  function defaultMockFactory({ emit }) {
    const jobs = [
      { job_id: "mock-job-1", status: "queued", progress: 0 },
      { job_id: "mock-job-1", status: "running", progress: 35 },
      { job_id: "mock-job-1", status: "running", progress: 72 },
      { job_id: "mock-job-1", status: "completed", progress: 100 },
    ];
    const events = [
      ["run", { run_id: "mock-run-1", status: "running", progress: 10 }],
      ["job", jobs[0]],
      ["billing", { item: "token_usage", cost: 0.02, currency: "USD" }],
      ["docs", { op: "add", path: "specs/mock.md" }],
      ["job", jobs[1]],
      ["run", { run_id: "mock-run-1", status: "running", progress: 68 }],
      ["job", jobs[2]],
      ["run", { run_id: "mock-run-1", status: "completed", progress: 100 }],
      ["job", jobs[3]],
      ["done", { status: "ok", run_id: "mock-run-1" }],
    ];
    const timers = [];
    events.forEach(([eventType, payload], index) => {
      timers.push(
        ((typeof window !== "undefined" && window.setTimeout) ? window.setTimeout.bind(window) : setTimeout)(() => {
          emit(eventType, payload);
        }, 250 * (index + 1))
      );
    });
    return {
      stop() {
        const cancelTimeout = (typeof window !== "undefined" && window.clearTimeout) ? window.clearTimeout.bind(window) : clearTimeout;
        timers.forEach((timerId) => cancelTimeout(timerId));
      },
    };
  }

  return {
    EventStreamClient,
    createUiEventStore,
    defaultMockFactory,
  };
});
