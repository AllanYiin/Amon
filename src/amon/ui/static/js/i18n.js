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
