const dictionary = {
  "nav.chat": "對話",
  "nav.context": "情境",
  "nav.graph": "流程圖",
  "nav.tools": "工具與技能",
  "nav.config": "設定",
  "nav.logs": "日誌與事件",
  "nav.docs": "文件",
  "nav.billing": "計費",
  "topbar.project": "專案",
  "topbar.toggleContext": "收合右側面板",
  "status.run.idle": "尚未有 Run",
  "status.run.running": "執行中",
  "status.run.completed": "已完成",
  "status.run.succeeded": "成功",
  "status.run.failed": "失敗",
  "status.run.error": "錯誤",
  "status.run.confirmRequired": "待確認",
  "status.run.unavailable": "不可用",
  "status.daemon.idle": "尚未連線",
  "status.daemon.connected": "已連線",
  "status.daemon.healthy": "Healthy",
  "status.daemon.reconnecting": "重新連線中",
  "status.daemon.unavailable": "Unavailable",
  "status.daemon.disconnected": "已中斷",
  "status.daemon.error": "錯誤",
  "status.node.idle": "閒置",
  "status.node.running": "執行中",
  "status.node.succeeded": "成功",
  "status.node.failed": "失敗",
  "status.node.skipped": "已跳過",
  "status.node.unavailable": "不可用",
  "empty.docs.title": "尚無文件",
  "action.deleteContext.confirmTitle": "確認刪除 Context",
};

export function t(key, fallback = "") {
  return dictionary[key] || fallback || key;
}

export function applyI18n(root = document) {
  root.querySelectorAll("[data-i18n]").forEach((node) => {
    const key = node.getAttribute("data-i18n");
    node.textContent = t(key, node.textContent);
  });
}
