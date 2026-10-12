# RaceState

A readable race-intelligence system, built one working slice at a time.
RaceState is the working project name; RaceSignal remains a possible public name.
This is an independent learning project, with no official F1 affiliation.

## What works today

Four fictional cars produce telemetry at 10 Hz. A bounded queue feeds one Python
worker thread, which updates an in-memory race state. A local HTTP API serves a
small responsive website with standings, a schematic oval, and selected-car
speed, throttle, brake and gear. The website polls at up to 5 Hz and remembers
its selected car. Everything is clearly labeled as simulated.

**This is milestone 0, not the distributed MVP.** State disappears on restart.
There is no Postgres, real feed, worker recovery, historical analytics or deployment yet.

## Run on macOS

Python 3.9+ and Git are sufficient. No packages, Node build, database or containers
are needed for this first slice. From the repository directory:

```bash
python3 -m venv .venv
source .venv/bin/activate
python3 -m racestate.server
```

Open http://127.0.0.1:8000. Press Ctrl-C to stop. If the port is occupied:

```bash
PORT=8001 python3 -m racestate.server
```

Configuration uses exported environment variables. `.env.example` documents them;
the app does not automatically load `.env`. Bind to localhost for this development server.

```bash
python3 -m unittest discover -s tests -v
```

## Disciplined MVP

The distributed MVP is complete at milestone 2:

- Simulated telemetry passes through bounded work to two worker processes.
- One authoritative state owner applies validated events and rejects late/duplicate data.
- Postgres stores replayable raw events and current driver state transactionally.
- The API reads consistent race snapshots; the browser shows order, position and driver telemetry.
- A reproducible replay proves ordering, persistence and restart behavior.

One session, fictional cars, no auth, predictions, news, radio or real feed in this MVP.
Target local behavior: 20 simulated cars at 10 events/sec each; state responses under
100 ms p95 and displayed readings under 500 ms old on a documented test machine.
These are acceptance targets, **not measured results**. Measure at milestone 1.

## Read the code in this order

1. `racestate/events.py`: immutable fields, units and validation.
2. `racestate/simulator.py`: deterministic event generation and backpressure.
3. `racestate/state.py`: ordering rules, lock and snapshot copies.
4. `racestate/worker.py`: queue consumption and shutdown.
5. `racestate/server.py`: wiring, HTTP routes and lifecycle.
6. `web/app.js`: one polling loop and explicit DOM updates.

Python handles the first implementation; SQL arrives with Postgres and Bash is
used for small operational commands. Java or C may be used when they solve a
specific problem James understands. Do not split into multiple languages just to
use them. Consider Go only after profiling identifies a service worth replacing.

## Structure

```text
racestate/                 domain model, simulation, worker, state, server
web/                       plain HTML/CSS and minimal browser JavaScript
tests/                     contract, state, queue and HTTP tests
docs/design-principles.md  constraints for every change
docs/architecture.md       boundaries, concurrency and migration path
docs/event-schema.md       wire contract, units, ordering and examples
docs/roadmap.md            milestones, dependencies and acceptance criteria
docs/github-plan.json      machine-readable GitHub planning items
scripts/publish_github.py  create private repo and sync milestones/issues
.github/workflows/ci.yml   Python test matrix
```

## GitHub setup

The local repository is ready to commit/push. GitHub creation needs an authenticated
GitHub CLI (`gh`) and a chosen owner. After restoring login, run:

```bash
gh auth login -h github.com
python3 scripts/publish_github.py OWNER/racestate
```

Replace `OWNER` with your personal username. The script creates a **private**
repository if missing, checks an existing repository is empty before the first
push, and creates milestones and issues from `docs/github-plan.json`. It will
not push to an unrelated existing repository. Reruns skip matching issue and
milestone titles. Existing issue bodies are not overwritten. Keep planning titles
stable when rerunning. Public release and licensing are separate decisions.

Use small branches and PRs tied to issues. Each PR should explain the problem,
changed behavior, how it was verified, and remaining limitations. Read each
important function before accepting the next architectural addition.

See [the roadmap](docs/roadmap.md), [architecture](docs/architecture.md),
[event contract](docs/event-schema.md) and [design principles](docs/design-principles.md).
