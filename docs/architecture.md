# Architecture

## Milestone 0: the executable slice

```text
simulator thread → Queue(maxsize=1000) → worker thread → RaceState
                                                          ↓ snapshot + lock
                                           local HTTP API → browser (5 Hz max)
```

All components run in one process. This is multithreaded, not distributed.
The simulator creates validated immutable events at 10 Hz for each fictional car.
A full queue blocks the producer with short timeouts. We do not silently drop events.
One worker owns mutations. RaceState uses a lock because HTTP request threads read
concurrently. It copies events under the lock and sorts the independent snapshot
after releasing it. Sequence is authoritative per (session, driver); equal or
older sequence numbers are ignored. New sessions require a new RaceState.

The API is read-only: `GET /api/state` returns a current snapshot, `GET /health`
reports HTTP process liveness. Health does **not** establish worker health or data
freshness. The browser derives freshness from source timestamps; clock skew must
be addressed before remote sources are supported. Static assets are an explicit
allowlist. The standard-library server is for the local demo, not production.

Shutdown sets a shared event, stops production and drains queued events. Thread
failure recovery is not implemented. A crash loses the queue and all state.
Synthetic progress defines order; it is not an official timing feed. The oval
and speed values are illustrative and are not a physical vehicle simulation.

## Boundaries that survive the next milestones

| Component | Owns | Must not own |
| --- | --- | --- |
| Source adapter | feed mapping, source metadata | UI, standings rules |
| Validation worker | normalization, bounds, valid event output | current state mutation |
| State reducer | ordering, current session state | network calls, browser code |
| Repository | transactions, event/checkpoint storage | presentation |
| API | snapshot serialization, read endpoints | telemetry production |
| Website | rendering, selected driver, freshness display | race calculations |

Milestone 0 combines adapter and validation for simplicity. Split them only when
introducing replay and multiple worker processes. Preserve a pure reducer and
small repository interface, rather than building generic infrastructure ahead of use.

## Milestone 1: prove one replay

Add a JSONL replay source, 20-car workload, metrics for queue depth/ingest lag/API
latency, and configurable polling. Establish measured acceptance results. Keep
one writer and no durable-distribution claims.

## Milestone 2: the distributed MVP

Use one local coordinator process, two Python validation worker processes and
bounded multiprocessing queues. The coordinator remains the sole state writer.
The API and coordinator stay in the same application initially; worker processes
are the first separate execution boundary, not separate microservices. This can
exercise process boundaries on one machine; multi-host execution waits until
there is a justified transport choice.

Introduce a Postgres repository using explicit SQL and a small Python driver.
Store raw events with unique `(session_id, driver_id, sequence)`, plus a latest
state table with the same ordering guard. Commit raw event insertion and latest
state upsert in one transaction. Raw events and persisted latest state are
canonical; an in-memory cache updates only after commit and rebuilds on startup.
Expose a coherent snapshot using a database transaction or one locked cache copy.

Workers may finish out of order. The reducer rejects stale updates; raw valid
history still records late events for replay. Drivers' sequences are independent,
so snapshots are latest-per-driver, not synchronized instants. Document this in
the UI and API. Snapshot consistency does not imply time alignment.

Replay from a deterministic fixture must produce identical final state after
restart. Without leases/retries, a worker crash can still lose in-flight tasks.
Fault recovery is explicitly milestone 3, not a hidden MVP guarantee.

## Milestone 3: fault tolerance and containers

Add a coordinator-owned task ledger, worker IDs and heartbeats, lease expiry,
at-least-once reassignment, bounded retry and dead-letter handling. Use a lease
generation token so late results from a previous owner cannot commit. Durable
task status and event/state updates must share a transaction before acknowledgement.
Test killing a worker during work, restarting the coordinator and reconnecting
the database. Avoid claiming exactly-once delivery: use idempotent writes.

Docker Compose will run app/workers and Postgres with health checks and a named
volume. Document readiness versus liveness, graceful shutdown, recovery windows,
backpressure and throughput. Only then consider multi-host coordination.

## Later boundaries

DuckDB queries Parquet exports of immutable session events for offline analysis;
it never competes with Postgres as the live source of truth. Real-data adapters
must establish availability, usage terms, latency, session identity and coordinate
mapping before integration. News/social context stores provenance, publication time
and fetch time separately; it cannot mutate telemetry. Production deployment adds
HTTPS, request limits, secrets, backups and monitoring after a host is chosen.
