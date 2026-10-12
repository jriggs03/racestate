> Current direction: [Phase 1 ingestion](phase-1-ingestion.md) supersedes
> the future Python coordinator and early Postgres plan below. Python ingests;
> Java will coordinate. The milestone 0 simulation remains supported.

# Roadmap

Milestones are ordered by dependency, not promised calendar dates. Finish and review one before expanding scope.

The starter implements milestone 0; all later milestones are planned. GitHub planning is generated from `docs/github-plan.json`.

## 0 — First vertical slice

Run the local simulation end to end.

### Review and accept the first slice

Run the demo and tests. Trace one event through all six documented components. Change the simulator speed and explain the effect. Acceptance: James can explain the flow and its crash limitations. Current starter implements the path; this issue tracks human review.

## 1 — Reproducible replay and measurements

Prove correctness and establish a performance baseline before distribution.

### Add strict JSONL telemetry replay

Parse external event fields strictly; reject unknown versions, missing fields and bad types. Add a 20-car fixture and configurable replay speed. Acceptance: repeated replay produces identical final state; malformed events are reported without invented readings.

### Measure local latency and freshness

Measure queue depth, ingestion lag and API p50/p95 at 200 events/sec. Acceptance: publish machine details and observed results against 100 ms API p95 / 500 ms display-age targets; document failures rather than assuming success.

## 2 — Postgres and worker processes

Complete the distributed MVP with one state owner and durable replay.

### Persist events and latest state in Postgres

Add explicit SQL migrations and a small repository interface. Use unique event keys and guarded latest-state upserts in one transaction. Acceptance: duplicates are idempotent; late events are retained in history without rollback; restart restores the same state.

### Run two validation worker processes

Add bounded process queues and a single coordinator/state writer. Acceptance: out-of-order completion cannot roll back state; browser works through Postgres-backed snapshots; document that in-flight crash recovery is deferred.

### Verify the distributed MVP end to end

Replay 20 cars through two workers, Postgres, API and browser. Acceptance: deterministic final state, coherent snapshots, responsive layout, selected-driver persistence, visible disconnect/staleness and published latency measurements.

## 3 — Recovery and containers

Make failure behavior deliberate and reproducible.

### Implement heartbeats, leases and task reassignment

Add durable task ledger, lease generations, heartbeat expiry, bounded retries and dead-letter handling. Acceptance: kill a worker in flight; replacement completes its task; stale owners cannot commit; restart does not lose acknowledged work.

### Containerize the application and Postgres

Add Dockerfiles and Compose only after process commands are stable. Acceptance: clean-machine startup, persistent volume, migrations, health/readiness distinction and documented graceful shutdown.

### Test database and coordinator failures

Inject database disconnects and coordinator restarts. Acceptance: no acknowledged event loss; duplicate retries are safe; backpressure stays bounded; recovery window is measured.

## 4 — Analytics and verified feeds

Add history without slowing the live path.

### Export Parquet and analyze with DuckDB

Export immutable events partitioned by session. Acceptance: schema/row counts match Postgres and an example SQL analysis runs without querying the live state path.

### Evaluate and integrate one real telemetry source

Verify current feed access, terms, latency, identifiers and coordinate mappings before choosing a provider. Acceptance: documented provenance and limits, adapter contract tests, replay fixture and explicit live/delayed labeling.

## 5 — Context, customization and deployment

Add useful fan context and operate a measured product.

### Add sourced news and social context

Evaluate API access and usage terms first. Store source URL, publication time, fetch time and dedupe key. Acceptance: attribution and stale labels; no context item can mutate telemetry.

### Add panel customization and deploy

Allow users to hide/reorder panels with local preferences. Choose a host and add HTTPS, request limits, secrets, backups and monitoring. Acceptance: measured browser latency and restore drill; profile before any Go rewrite.
