import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "src"))

from amon.domain import RunRecord
from amon.runtime_vnext import CheckpointStore
from amon.storage import RunRepository


class CheckpointStoreTests(unittest.TestCase):
    def test_write_and_load_latest_checkpoint(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp)
            run_repo = RunRepository(project_root)
            run_repo.create(RunRecord.create(run_id="run-001", workflow_ref="workflow.demo", status="running"))
            store = CheckpointStore(project_root)

            written = store.write("run-001", phase="running", node_id="n1", status="running", payload={"offset": 7})
            loaded = store.load("run-001")
            run = run_repo.get("run-001")

            self.assertEqual(loaded["checkpoint_id"], written["checkpoint_id"])
            self.assertEqual(loaded["node_id"], "n1")
            self.assertEqual(loaded["payload"]["offset"], 7)
            self.assertEqual(run.checkpoint_state["last_checkpoint_id"], written["checkpoint_id"])


if __name__ == "__main__":
    unittest.main()
