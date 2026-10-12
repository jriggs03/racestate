# Phase 1: OpenF1 ingestion

This phase follows the revised architecture agreed with James. Python ingests
and normalizes; Java will own the coordinator and distributed processing later.
There are no Java workers, brokers, Postgres, DuckDB or deployment changes here.
The existing simulation website remains a separate demo and still says simulated.

## Trace one batch

```text
OpenF1 REST → raw response bytes → validate and normalize every record
                                           ↓ one SQLite transaction
                                events + raw archive outbox
                                  ↓                 ↓ separate command
                         read by log offset     local files OR Amazon S3
                                  ↓
                         future Java coordinator
```

SQLite is included with Python and gives us transactions, durable commits and a
unique event-ID constraint without running a service. JSONL would be simpler to
inspect directly but would require handling torn appends, duplicate indexing and
an atomic archive queue ourselves. The small EventLog protocol describes the
append/read boundary; SQLiteEventLog is its only implementation. This local log
is not the future Postgres state store or DuckDB analytics layer.

## Run it

Python 3.9+; no installation needed for local ingestion. Run from the repo root:

```bash
python3 -m venv .venv
source .venv/bin/activate
cp .env.example .env
# The file is shell syntax; inspect it before sourcing. Keep credentials out of Git.
set -a
source .env
set +a
python3 -m racestate.ingestion ingest --session 9159 --driver 55 \
  --start 2023-09-15T13:08:19Z --end 2023-09-15T13:08:21Z
python3 -m racestate.ingestion read --after 0 --limit 10
python3 -m racestate.ingestion archive --target local
python3 -m unittest discover -s tests -v
```

The first command requests historical car data. To ingest race positions, use
`--endpoint position` with a suitable session/time range. Both endpoints require
an explicit positive numeric session; we avoid `latest` because it can switch
sessions between requests. Requests cover [start, end), up to five minutes.
Choose smaller windows for car data across all drivers. A response above 20 MiB
is rejected, with no partial commit; narrow the query and retry.

OpenF1 historical data since 2023 is free; live access requires a subscription.
See https://openf1.org/ and https://openf1.org/docs/ for availability, fields,
limits and access. OPENF1_TOKEN accepts a bearer token obtained from the provider;
this phase does not implement login or token refresh. Never log the token.
The command fetches one window, not an automatic continuous polling service.
Repeat windows deliberately; overlaps deduplicate. Respect the provider's rate
limits (currently 30 requests/minute for free historical access). Temporary
network/429/5xx failures get at most three attempts; auth failures fail immediately.

## Optional S3 archive

Create/configure your bucket separately. Install the optional AWS SDK and use an
AWS profile or the normal AWS credential provider chain:

```bash
python3 -m pip install -r requirements-s3.txt
export AWS_PROFILE=racestate
export RACESTATE_S3_BUCKET=your-existing-bucket
python3 -m racestate.ingestion archive --target s3
```

The credentials need `s3:PutObject` for the bucket's `openf1/*` prefix (and KMS
permissions if required by your bucket). The uploader stores the exact successful
response bytes as JSON at `openf1/session=9159/car_data/<sha256-of-raw-body>.json`.
No API tokens, request headers or AWS secrets are placed in the object.

Archival is optional and explicit. Ingest never calls AWS. When credentials are
absent, continue ingesting and use local archives or leave batches queued. If an
upload fails, the command fails and that batch stays pending. Earlier successful
uploads remain marked. Retry the command after fixing AWS access. A crash between
upload and marking may upload the same bytes/key twice; this is safe replacement,
not exactly-once delivery. Versioned buckets may retain multiple versions.

Local and S3 are alternative archive destinations for this phase: the outbox has
one completion flag, not one per destination. Draining locally marks those batches
complete; changing to S3 later will not automatically copy them. Keep the log and
local archive, or use a separate log path when experimenting with destinations.

## Contract and ordering

`SourceEvent` contains schema_version, source, event_type, event_id, session_key,
driver_number, occurred_at (UTC ISO timestamp), source_sequence and a typed payload.
CarData uses speed_kph, throttle_fraction (0..1), brake (boolean), gear, rpm and
drs_code. PositionData contains the reported position. We preserve raw bytes and
do not infer track coordinates, lap progress, team membership or DRS meanings.

SHA-256 hashes canonical normalized fields, including source, schema version,
endpoint, session, driver, UTC time and payload. Arrival time, JSON key order and
log offsets are excluded. Equivalent normalized readings have identical IDs
across restarts. Changed readings at the same timestamp get different IDs; a
future coordinator must define its correction policy. Unknown extra source fields
are retained in raw bytes but excluded from normalized IDs. Changing normalization
semantics requires a deliberate schema-version decision.

OpenF1 REST supplies no sequence; source_sequence is null. The log assigns a
monotonically increasing global offset on insertion; gaps are allowed after
ignored duplicates. Within each batch we sort by source time, driver and ID.
Across batches offsets describe commit order, not race chronology. Late events
are retained. Java should consume `read_after(last_processed_offset)` and save its
checkpoint only after processing succeeds. This phase has no consumer checkpoint,
acknowledgement, Java transport, leases or worker fault recovery. `read` emits JSON
lines as a manual handoff/replay inspection format.

## Failure and storage boundaries

A malformed record or wrong session rejects the whole batch before commit. Fix
the adapter/query and fetch again; rejected HTTP bodies are not archived in this
phase. No source cursor advances automatically. Valid events and raw outbox bytes
commit together or roll back together. Re-fetching a committed batch inserts no
duplicate normalized events. Byte-identical raw bodies share an archive key.

WAL and synchronous=FULL ask SQLite to persist committed transactions on local
disk. Tests cover reopen, abrupt process exit after commit, transaction rollback,
deduplication and failed archive retry. These do not prove resilience to hardware
loss. Use a local filesystem, keep the SQLite database plus WAL together, and use
SQLite-aware backups; do not copy a database file alone while it is being written.
One ingestion process and one optional archive process are sufficient; no shared
network filesystem or distributed log guarantee is claimed.

Reads and uploads are bounded to 100 entries by default (reads allow up to 1000).
Uploaded raw bytes remain in SQLite intentionally for audit/recovery. There is no
retention or disk quota automation yet: monitor available space, back up, and
stop ingestion before the disk fills. A failed database commit is surfaced rather
than treated as accepted data.

## Suggested reading order

1. models.py: typed fields, validation, stable event identity.
2. openf1.py: URL filters, response limits and bounded retries.
3. pipeline.py: normalize, sort, form archive key, commit.
4. log.py: schema, transaction, offset reads, archive queue.
5. archive.py: local/S3 writes and retry-safe completion.
6. config.py and __main__.py: environment and command wiring.

All files above are under `racestate/ingestion/`. Tests are in
`tests/test_ingestion.py`; AWS calls use a fake client, not a real bucket.
