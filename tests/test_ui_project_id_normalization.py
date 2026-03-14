import subprocess
import textwrap
import unittest
from pathlib import Path


class UIProjectIdNormalizationTests(unittest.TestCase):
    def _run_node(self, script: str) -> None:
        completed = subprocess.run(
            ["node", "-e", script],
            cwd=Path(__file__).resolve().parents[1],
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

    def test_virtual_project_id_is_not_treated_as_real_project(self) -> None:
        script = textwrap.dedent(
            """
            (async () => {
              const path = require('node:path');
              const { pathToFileURL } = require('node:url');
              const fileUrl = pathToFileURL(path.resolve('src/amon/ui/static/js/domain/projectId.js')).href;
              const { VIRTUAL_PROJECT_ID, isVirtualProjectId, normalizeProjectIdForUi, hasConcreteProjectId } = await import(fileUrl);

              if (VIRTUAL_PROJECT_ID !== '__virtual__') {
                throw new Error(`unexpected virtual id constant: ${VIRTUAL_PROJECT_ID}`);
              }
              if (!isVirtualProjectId('__virtual__')) {
                throw new Error('virtual project id should be detected');
              }
              if (normalizeProjectIdForUi('__virtual__') !== '') {
                throw new Error('virtual project id should normalize to empty string');
              }
              if (hasConcreteProjectId('__virtual__')) {
                throw new Error('virtual project id should not be treated as a concrete project');
              }
              if (normalizeProjectIdForUi('proj-real') !== 'proj-real') {
                throw new Error('real project id should stay unchanged');
              }
              if (!hasConcreteProjectId('proj-real')) {
                throw new Error('real project id should stay concrete');
              }
            })().catch((error) => {
              console.error(error);
              process.exit(1);
            });
            """
        )
        self._run_node(script)
