import { setStatusText } from "../domain/status.js";
import { t } from "../i18n.js";

const LEVEL_BY_PILL = {
  run: "neutral",
  daemon: "neutral",
};

export function createHeaderLayout({ elements, store }) {
  function renderProjectOptions(projectSelect, projects = []) {
    if (!projectSelect) return;
    const selected = projectSelect.value;
    projectSelect.innerHTML = "";

    const emptyOption = document.createElement("option");
    emptyOption.value = "";
    emptyOption.textContent = t("topbar.noProject", "無專案");
    projectSelect.appendChild(emptyOption);

    projects.forEach((project) => {
      const option = document.createElement("option");
      option.value = project.project_id;
      option.textContent = `${project.name}（${project.project_id}）`;
      projectSelect.appendChild(option);
    });

    projectSelect.value = selected;
  }

  function render(snapshot = {}) {
    const layout = snapshot.layout || {};
    const projects = Array.isArray(layout.projects) ? layout.projects : [];

    renderProjectOptions(elements.projectSelect, projects);
    if (elements.projectSelect) {
      elements.projectSelect.value = layout.projectId || "";
    }

    const run = layout.runPill || { text: t("status.run.idle"), level: LEVEL_BY_PILL.run, title: t("tooltip.runIdle") };
    const daemon = layout.daemonPill || { text: t("status.daemon.idle"), level: LEVEL_BY_PILL.daemon, title: t("tooltip.daemonIdle") };
    const budget = layout.budgetPill || "Budget：NT$ 0.00 / NT$ 5,000";

    setStatusText(elements.shellRunStatus, run.text, run.level || LEVEL_BY_PILL.run, run.title || "");
    setStatusText(elements.shellDaemonStatus, daemon.text, daemon.level || LEVEL_BY_PILL.daemon, daemon.title || "");
    if (elements.shellBudgetStatus) {
      elements.shellBudgetStatus.textContent = budget;
    }
  }

  function mount() {
    const unsubscribe = store.subscribe(render);
    render(store.getState());
    return () => unsubscribe();
  }

  return { mount, render };
}
