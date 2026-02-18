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

            class FakeEventSource {
              constructor(_url) {
                this.listeners = new Map();
                setTimeout(() => {
                  const emit = (eventType, payload) => {
                    const handler = this.listeners.get(eventType);
                    if (handler) {
                      handler({ data: JSON.stringify(payload), lastEventId: null });
                    }
                  };
                  emit('run', { run_id: 'run-1', status: 'running', progress: 15 });
                  emit('job', { job_id: 'job-1', status: 'running', progress: 40 });
                  emit('billing', { item: 'token_usage', cost: 1.25, currency: 'USD' });
                  emit('docs', { op: 'add', path: 'docs/design.md' });
                  emit('done', { status: 'ok' });
                }, 0);
              }
              addEventListener(eventType, callback) { this.listeners.set(eventType, callback); }
              close() {}
            }
            global.EventSource = FakeEventSource;

            const client = new EventStreamClient({
              preferSSE: true,
              sseUrlBuilder: () => '/v1/chat/stream?message=demo',
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

            class FakeEventSource {
              constructor(_url) {
                this.listeners = new Map();
                setTimeout(() => {
                  const run = this.listeners.get('run');
                  if (run) {
                    run({ data: JSON.stringify({ run_id: 'run-2' }), lastEventId: 'evt-99' });
                  }
                }, 0);
              }
              addEventListener(eventType, callback) { this.listeners.set(eventType, callback); }
              close() {}
            }
            global.EventSource = FakeEventSource;

            const client = new EventStreamClient({
              preferSSE: true,
              sseUrlBuilder: () => '/v1/chat/stream?message=resume+me',
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

    def test_sse_error_event_stops_reconnect(self) -> None:
        script = textwrap.dedent(
            """
            const { EventStreamClient } = require('./src/amon/ui/event_stream_client.js');

            let instances = 0;
            class FakeEventSource {
              constructor(_url) {
                instances += 1;
                this.listeners = new Map();
                setTimeout(() => {
                  const handler = this.listeners.get('error');
                  if (handler) {
                    handler({ data: JSON.stringify({ message: 'node timeout' }), lastEventId: 'evt-2' });
                  }
                  if (typeof this.onerror === 'function') {
                    this.onerror(new Error('closed'));
                  }
                }, 0);
              }

              addEventListener(eventType, callback) {
                this.listeners.set(eventType, callback);
              }

              close() {}
            }

            global.EventSource = FakeEventSource;

            const client = new EventStreamClient({
              preferSSE: true,
              maxReconnectAttempts: 5,
              sseUrlBuilder: () => '/v1/chat/stream?message=demo',
            });

            client.start({ message: 'demo' });

            setTimeout(() => {
              if (instances !== 1) {
                throw new Error(`EventSource should not reconnect after error event, got ${instances}`);
              }
              process.exit(0);
            }, 30);
            """
        )
        self._run_node(script)

    def test_done_event_ignores_followup_onerror_without_reconnect(self) -> None:
        script = textwrap.dedent(
            """
            const { EventStreamClient } = require('./src/amon/ui/event_stream_client.js');

            let instances = 0;
            const statuses = [];
            class FakeEventSource {
              constructor(_url) {
                instances += 1;
                this.listeners = new Map();
                setTimeout(() => {
                  const done = this.listeners.get('done');
                  if (done) {
                    done({ data: JSON.stringify({ status: 'ok' }), lastEventId: 'evt-done' });
                  }
                  if (typeof this.onerror === 'function') {
                    this.onerror(new Error('connection closed'));
                  }
                }, 0);
              }

              addEventListener(eventType, callback) {
                this.listeners.set(eventType, callback);
              }

              close() {}
            }

            global.EventSource = FakeEventSource;

            const client = new EventStreamClient({
              preferSSE: true,
              maxReconnectAttempts: 5,
              reconnectBaseMs: 1,
              reconnectMaxMs: 1,
              sseUrlBuilder: () => '/v1/chat/stream?message=demo',
              onStatusChange: ({ status }) => statuses.push(status),
            });

            client.start({ message: 'demo' });

            setTimeout(() => {
              if (instances !== 1) {
                throw new Error(`done event should stop reconnect, got ${instances} connections`);
              }
              if (statuses.includes('error') || statuses.includes('reconnecting')) {
                throw new Error(`unexpected status transitions: ${statuses.join(',')}`);
              }
              process.exit(0);
            }, 30);
            """
        )
        self._run_node(script)


    def test_reasoning_event_is_dispatched(self) -> None:
        script = textwrap.dedent(
            """
            const { EventStreamClient } = require('./src/amon/ui/event_stream_client.js');

            let seenReasoning = '';
            class FakeEventSource {
              constructor(_url) {
                this.listeners = new Map();
                setTimeout(() => {
                  const emit = (eventType, payload) => {
                    const handler = this.listeners.get(eventType);
                    if (handler) {
                      handler({ data: JSON.stringify(payload), lastEventId: null });
                    }
                  };
                  emit('reasoning', { text: '先分解問題再輸出' });
                  emit('done', { status: 'ok' });
                }, 0);
              }
              addEventListener(eventType, callback) { this.listeners.set(eventType, callback); }
              close() {}
            }
            global.EventSource = FakeEventSource;

            const client = new EventStreamClient({
              preferSSE: true,
              sseUrlBuilder: () => '/v1/chat/stream?message=demo',
              onEvent: (eventType, payload) => {
                if (eventType === 'reasoning') {
                  seenReasoning = payload.text || '';
                }
              },
            });

            client.start({ message: 'demo' });

            setTimeout(() => {
              if (seenReasoning !== '先分解問題再輸出') {
                throw new Error(`reasoning event missing: ${seenReasoning}`);
              }
              process.exit(0);
            }, 20);
            """
        )
        self._run_node(script)

    def test_reconnect_request_reuses_project_and_chat_from_events(self) -> None:
        script = textwrap.dedent(
            """
            const { EventStreamClient } = require('./src/amon/ui/event_stream_client.js');

            const urls = [];
            let instanceId = 0;
            class FakeEventSource {
              constructor(url) {
                instanceId += 1;
                this.id = instanceId;
                urls.push(url);
                this.listeners = new Map();
                setTimeout(() => {
                  if (this.id === 1) {
                    const notice = this.listeners.get('notice');
                    if (notice) {
                      notice({ data: JSON.stringify({ project_id: 'proj-1', chat_id: 'chat-1' }), lastEventId: 'evt-1' });
                    }
                    if (typeof this.onerror === 'function') {
                      this.onerror(new Error('network drop'));
                    }
                  }
                }, 0);
              }

              addEventListener(eventType, callback) {
                this.listeners.set(eventType, callback);
              }

              close() {}
            }

            global.EventSource = FakeEventSource;

            const client = new EventStreamClient({
              preferSSE: true,
              reconnectBaseMs: 1,
              reconnectMaxMs: 1,
              maxReconnectAttempts: 1,
              sseUrlBuilder: (params, lastEventId) => {
                const query = new URLSearchParams({ message: params.message || '' });
                if (params.project_id) query.set('project_id', params.project_id);
                if (params.chat_id) query.set('chat_id', params.chat_id);
                if (lastEventId) query.set('last_event_id', lastEventId);
                return `/v1/chat/stream?${query.toString()}`;
              },
            });

            client.start({ message: '請協助擬定嘉義縣青年返鄉政策' });

            setTimeout(() => {
              if (urls.length < 2) {
                throw new Error(`expected reconnect request, got ${urls.length}`);
              }
              if (!urls[1].includes('project_id=proj-1')) {
                throw new Error(`reconnect request missing project_id: ${urls[1]}`);
              }
              if (!urls[1].includes('chat_id=chat-1')) {
                throw new Error(`reconnect request missing chat_id: ${urls[1]}`);
              }
              process.exit(0);
            }, 40);
            """
        )
        self._run_node(script)


if __name__ == "__main__":
    unittest.main()
