export const runStatus = Object.freeze({
  IDLE: "idle",
  RUNNING: "running",
  COMPLETED: "completed",
  SUCCEEDED: "succeeded",
  FAILED: "failed",
  ERROR: "error",
  CONFIRM_REQUIRED: "confirm_required",
  UNAVAILABLE: "unavailable",
});

export const nodeStatus = Object.freeze({
  IDLE: "idle",
  RUNNING: "running",
  SUCCEEDED: "succeeded",
  FAILED: "failed",
  SKIPPED: "skipped",
  UNAVAILABLE: "unavailable",
});

export const daemonStatus = Object.freeze({
  IDLE: "idle",
  CONNECTED: "connected",
  HEALTHY: "healthy",
  RECONNECTING: "reconnecting",
  DISCONNECTED: "disconnected",
  UNAVAILABLE: "unavailable",
  ERROR: "error",
});

export const statusPillClassMap = Object.freeze({
  success: "pill--success",
  warning: "pill--warning",
  danger: "pill--danger",
  neutral: "pill--neutral",
});

export const runStatusPillLevelMap = Object.freeze({
  [runStatus.SUCCEEDED]: "success",
  [runStatus.COMPLETED]: "success",
  success: "success",
  ok: "success",
  [runStatus.ERROR]: "danger",
  [runStatus.FAILED]: "danger",
  [runStatus.UNAVAILABLE]: "danger",
  [runStatus.CONFIRM_REQUIRED]: "warning",
  warning: "warning",
  degraded: "warning",
});

export const daemonStatusPillLevelMap = Object.freeze({
  [daemonStatus.CONNECTED]: "success",
  [daemonStatus.HEALTHY]: "success",
  [daemonStatus.RECONNECTING]: "warning",
  [daemonStatus.DISCONNECTED]: "danger",
  [daemonStatus.UNAVAILABLE]: "danger",
  [daemonStatus.ERROR]: "danger",
});

export const statusI18nKeyMap = Object.freeze({
  run: {
    idle: "status.run.idle",
    running: "status.run.running",
    completed: "status.run.completed",
    succeeded: "status.run.succeeded",
    failed: "status.run.failed",
    error: "status.run.error",
    confirm_required: "status.run.confirmRequired",
    unavailable: "status.run.unavailable",
  },
  daemon: {
    idle: "status.daemon.idle",
    connected: "status.daemon.connected",
    healthy: "status.daemon.healthy",
    reconnecting: "status.daemon.reconnecting",
    unavailable: "status.daemon.unavailable",
    disconnected: "status.daemon.disconnected",
    error: "status.daemon.error",
  },
  node: {
    idle: "status.node.idle",
    running: "status.node.running",
    succeeded: "status.node.succeeded",
    failed: "status.node.failed",
    skipped: "status.node.skipped",
    unavailable: "status.node.unavailable",
  },
});
