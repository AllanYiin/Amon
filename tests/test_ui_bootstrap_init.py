import shutil
import subprocess
import textwrap
import unittest


@unittest.skipIf(shutil.which("node") is None, "node is required for UI bootstrap init tests")
class UIBootstrapInitTests(unittest.TestCase):
    def _run_node(self, script: str) -> None:
        completed = subprocess.run(
            ["node", "--input-type=module", "-e", script],
            capture_output=True,
            text=True,
            check=False,
        )
        if completed.returncode != 0:
            self.fail(
                "Node script failed\n"
                f"stdout:\n{completed.stdout}\n"
                f"stderr:\n{completed.stderr}"
            )

    def test_bootstrap_continues_to_route_when_project_load_fails(self) -> None:
        script = textwrap.dedent(
            """
            import { runBootstrapInitialization } from './src/amon/ui/static/js/core/bootstrapInit.js';

            const calls = [];
            const toasts = [];

            await runBootstrapInitialization({
              loadProjects: async () => {
                throw new Error('讀取runs資料失敗：Failed to fetch');
              },
              setProjectState: (projectId) => calls.push(['setProjectState', projectId]),
              refreshUiPreferences: async (projectId) => calls.push(['refreshUiPreferences', projectId]),
              updateThinking: (payload) => calls.push(['updateThinking', payload.status, payload.brief]),
              hydrateSelectedProject: async () => calls.push(['hydrateSelectedProject']),
              resolveRouteFromHash: () => 'chat',
              navigateToRoute: (routeKey) => calls.push(['navigateToRoute', routeKey]),
              applyRoute: async (routeKey) => calls.push(['applyRoute', routeKey]),
              showToast: (message, duration, type) => toasts.push({ message, duration, type }),
              getProjectId: () => null,
              hasLocationHash: () => false,
            });

            if (!toasts.some((item) => item.message.includes('載入專案清單失敗：讀取runs資料失敗：Failed to fetch'))) {
              throw new Error(`expected toast not found: ${JSON.stringify(toasts)}`);
            }
            if (!calls.some((entry) => entry[0] === 'navigateToRoute' && entry[1] === 'chat')) {
              throw new Error(`chat route was not mounted after load failure: ${JSON.stringify(calls)}`);
            }
            if (!calls.some((entry) => entry[0] === 'hydrateSelectedProject')) {
              throw new Error(`hydrateSelectedProject should still run: ${JSON.stringify(calls)}`);
            }
            """
        )
        self._run_node(script)

    def test_bootstrap_uses_apply_route_when_hash_exists(self) -> None:
        script = textwrap.dedent(
            """
            import { runBootstrapInitialization } from './src/amon/ui/static/js/core/bootstrapInit.js';

            const calls = [];

            await runBootstrapInitialization({
              loadProjects: async () => calls.push(['loadProjects']),
              setProjectState: () => calls.push(['setProjectState']),
              refreshUiPreferences: async () => calls.push(['refreshUiPreferences']),
              updateThinking: () => calls.push(['updateThinking']),
              hydrateSelectedProject: async () => calls.push(['hydrateSelectedProject']),
              resolveRouteFromHash: () => 'chat',
              navigateToRoute: (routeKey) => calls.push(['navigateToRoute', routeKey]),
              applyRoute: async (routeKey) => calls.push(['applyRoute', routeKey]),
              showToast: () => {},
              getProjectId: () => null,
              hasLocationHash: () => true,
            });

            if (!calls.some((entry) => entry[0] === 'applyRoute' && entry[1] === 'chat')) {
              throw new Error(`applyRoute was not used: ${JSON.stringify(calls)}`);
            }
            if (calls.some((entry) => entry[0] === 'navigateToRoute')) {
              throw new Error(`navigateToRoute should not be used when hash exists: ${JSON.stringify(calls)}`);
            }
            """
        )
        self._run_node(script)


if __name__ == "__main__":
    unittest.main()
