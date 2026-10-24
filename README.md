# RaceState

Collects F1 events with durable storage and replay.

Independent project by James Riggs. Built with Python, SQLite, and a small browser UI.
This is an independent learning project with no official F1 affiliation.

## Current implementation

RaceState currently has two working pieces:

- A real-data ingestion path that fetches historical OpenF1 car and position data, validates and normalizes records, and writes them to a durable SQLite event log.
- A separate simulated browser demo that shows fictional telemetry through a small local API and UI.

The ingestion path uses deterministic event IDs for deduplication, monotonically increasing log offsets for replay, SQLite WAL mode for durable local commits, and an outbox for raw-response archival to local files or Amazon S3. Automated tests cover reopen behavior, rollback, deduplication, abrupt exit after commit, and failed archive retry.

**Not implemented yet:** the Java coordinator/workers, Postgres state store, DuckDB analytics layer, and distributed worker fault recovery. Those are future phases of the project.

## Phase 1: real-data ingestion

The current architecture is:

```text
OpenF1 REST
    ↓
Python validation + normalization
    ↓
SQLite event log + raw archive outbox
    ↓                         ↓
replay by log offset      local files or S3
    ↓
future Java coordinator
```

See [the Phase 1 ingestion guide](docs/phase-1-ingestion.md) for commands, configuration, event contracts, ordering rules, archival behavior, and failure boundaries.

## Simulation demo

Four fictional cars produce telemetry at 10 Hz. A bounded queue feeds one Python worker thread, which updates an in-memory race state. A local HTTP API serves a responsive browser UI with standings, a schematic track view, and selected-car telemetry.

**The browser demo is simulated.** Its in-memory state disappears on restart. It is separate from the durable OpenF1 ingestion path.

### Run the demo

Python 3.9+ and Git are sufficient:

```bash
python3 -m venv .venv
source .venv/bin/activate
python3 -m racestate.server
```

Open `http://127.0.0.1:8000`.

Run tests with:

```bash
python3 -m unittest discover -s tests -v
```

## Read the code

For the real-data ingestion path, start here:

1. `racestate/ingestion/models.py` — typed fields, validation, and stable event identity.
2. `racestate/ingestion/openf1.py` — OpenF1 requests, response limits, and retries.
3. `racestate/ingestion/pipeline.py` — normalization, ordering, and commit flow.
4. `racestate/ingestion/log.py` — SQLite schema, transactions, offsets, and archive queue.
5. `racestate/ingestion/archive.py` — local/S3 archival and retry behavior.
6. `racestate/ingestion/config.py` and `__main__.py` — configuration and command wiring.

For the simulated browser demo:

1. `racestate/events.py`
2. `racestate/simulator.py`
3. `racestate/state.py`
4. `racestate/worker.py`
5. `racestate/server.py`
6. `web/app.js`

## Project direction

The current phase deliberately keeps ingestion local and durable before adding distributed processing. Future work will connect the event log to a Java coordinator, add worker registration and failure handling, and introduce Postgres and DuckDB only when those components are actually implemented and tested.

See the [roadmap](docs/roadmap.md), [architecture](docs/architecture.md), [event contract](docs/event-schema.md), and [design principles](docs/design-principles.md) for more detail.
