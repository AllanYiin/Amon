import subprocess
import textwrap
import unittest
from pathlib import Path


class UIEventStreamClientTests(unittest.TestCase):
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

    def test_events_are_received_and_applied_to_store(self) -> None:
        script = textwrap.dedent(
            """
            const { EventStreamClient, createUiEventStore } = require('./src/amon/ui/event_stream_client.js');
            const store = createUiEventStore();
            const client = new EventStreamClient({
              useMock: true,
              mockFactory: ({ emit }) => {
                emit('run', { run_id: 'run-1', status: 'running', progress: 15 });
                emit('job', { job_id: 'job-1', status: 'running', progress: 40 });
                emit('billing', { item: 'token_usage', cost: 1.25, currency: 'USD' });
                emit('docs', { op: 'add', path: 'docs/design.md' });
                emit('done', { status: 'ok' });
                return { stop() {} };
              },
              onEvent: (eventType, payload) => store.applyEvent(eventType, payload),
            });

            client.start({ message: 'demo' });

            setTimeout(() => {
              const snapshot = store.getState();
              if (!snapshot.run || snapshot.run.run_id !== 'run-1') {
                throw new Error('run state was not updated');
              }
              if (!snapshot.jobs['job-1'] || snapshot.jobs['job-1'].progress !== 40) {
                throw new Error('job state was not updated');
              }
              if (snapshot.billing.total_cost !== 1.25) {
                throw new Error('billing total_cost was not accumulated');
              }
              if (!snapshot.docs.includes('docs/design.md')) {
                throw new Error('docs state was not updated');
              }
              process.exit(0);
            }, 10);
            """
        )
        self._run_node(script)

    def test_last_event_id_is_retained_for_resume(self) -> None:
        script = textwrap.dedent(
            """
            const { EventStreamClient } = require('./src/amon/ui/event_stream_client.js');
            let observedLastEventId = null;
            const client = new EventStreamClient({
              useMock: true,
              mockFactory: ({ emit }) => {
                emit('run', { run_id: 'run-2', last_event_id: 'evt-99' });
                return { stop() {} };
              },
              onEvent: (_eventType, _payload, lastEventId) => {
                observedLastEventId = lastEventId;
              },
            });

            client.start({ message: 'resume me' });

            setTimeout(() => {
              if (observedLastEventId !== 'evt-99') {
                throw new Error(`unexpected last_event_id: ${observedLastEventId}`);
              }
              process.exit(0);
            }, 10);
            """
        )
        self._run_node(script)


if __name__ == "__main__":
    unittest.main()
