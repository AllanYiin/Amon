import { createRunsService } from "./runsService.js";
import { createDocsService } from "./docsService.js";
import { createArtifactsService } from "./artifactsService.js";
import { createBillingService } from "./billingService.js";
import { createContextService } from "./contextService.js";
import { createLogsService } from "./logsService.js";
import { createGraphService } from "./graphService.js";

function withReadableErrors(serviceName, service) {
  return Object.fromEntries(
    Object.entries(service).map(([name, fn]) => {
      if (typeof fn !== "function") return [name, fn];
      return [
        name,
        async (...args) => {
          try {
            return await fn(...args);
          } catch (error) {
            console.error(`[${serviceName}.${name}]`, error);
            const detail = error?.message || "未知錯誤";
            throw new Error(`讀取${serviceName}資料失敗：${detail}`);
          }
        },
      ];
    })
  );
}

export function createServices({ api }) {
  return {
    runs: withReadableErrors("runs", createRunsService({ api })),
    docs: withReadableErrors("docs", createDocsService({ api })),
    artifacts: withReadableErrors("artifacts", createArtifactsService({ api })),
    billing: withReadableErrors("billing", createBillingService({ api })),
    context: withReadableErrors("context", createContextService({ api })),
    logs: withReadableErrors("logs", createLogsService({ api })),
    graph: withReadableErrors("graph", createGraphService({ api })),
  };
}
