# Migration V3 Plan (Legacy Runtime + TaskGraph2 Removal)

## Goal
- Remove both legacy graph runtime and TaskGraph2 runtime from the codebase.
- Converge to a single graph execution runtime path with stable behavior and deterministic tests.
- Keep externally observable behavior unchanged throughout migration stages unless explicitly approved.

## Stage Plan

### Stage 0 — Baseline & Hard Gates
- Establish baseline test results and known failures.
- Add anti-legacy scanning script in **WARN** mode.
- Add CI target `check:no_legacy_graph` that runs scanner without breaking existing pipeline.
- Document current runtime entrypoint and import surfaces.

### Stage 1 — Inventory & Coverage Mapping
- Build complete inventory of legacy + TaskGraph2 callsites.
- Tag each callsite by risk (CLI/UI/hooks/tests/internal).
- Map existing tests to callsites and identify missing deterministic coverage.

### Stage 2 — Single Entrypoint Contract Freeze
- Define and freeze runtime contract for the future unified path.
- Add characterization tests for current behavior that must remain stable.
- Block new legacy/runtime split callsites via scanner expansion.

### Stage 3 — Internal Routing Consolidation
- Route execution through unified internal dispatcher while preserving API signatures.
- Keep feature flags/opt-in guards where needed to minimize rollout risk.
- Validate parity with existing characterization tests.

### Stage 4 — Legacy Runtime Callsite Removal
- Remove direct legacy runtime construction/usages from production code.
- Keep temporary compatibility wrappers only if still required by unchanged public API.
- Add migration notes for impacted internals.

### Stage 5 — TaskGraph2 Runtime Callsite Removal
- Remove TaskGraph2-specific runtime entrypoint usages from production code.
- Ensure planner/execution path continues to satisfy existing output contracts.
- Expand deterministic tests for continuation and graph execution flows.

### Stage 6 — Gate Tightening (WARN → FAIL)
- Switch anti-legacy script mode to **FAIL** in CI once code references are eliminated.
- Fail PRs introducing new legacy/taskgraph2 runtime references.
- Keep explicit allowlist only if documented and time-bounded.

### Stage 7 — Cleanup & Final Verification
- Remove dead code, outdated docs, and obsolete tests.
- Confirm all migration deliverables and guardrails are active.
- Publish final migration report with before/after architecture summary.

## Definition of Done (Final Stage)
- No production/runtime code references to legacy runtime modules.
- No production/runtime code references to TaskGraph2 runtime modules.
- `check:no_legacy_graph` passes in **FAIL** mode with zero matches.
- Full test suite passes (including continuation guard set) with deterministic outcomes.
- Runtime entrypoint documentation reflects the final unified design.
