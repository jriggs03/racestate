# Telemetry contract v1

Current representation: frozen Python `TelemetryEvent`; JSON serialization uses
the exact same field names. Validation lives in `racestate/events.py`. External
JSON parsing and adapter-level checks are planned, not currently implemented.

| Field | Type / units | Rule |
| --- | --- | --- |
| schema_version | integer | 1 |
| session_id | string | nonempty, source-scoped session identity |
| driver_id | string | nonempty, stable within session |
| sequence | integer | >= 0, strictly increasing per session/driver at source |
| timestamp | number, Unix UTC seconds | finite, >= 0; source observation time |
| progress | number, laps | finite, >= 0; completed laps plus fraction |
| speed_kph | number, km/h | finite, 0..400 |
| throttle | number, fraction | finite, 0..1 |
| brake | boolean | applied/not applied |
| gear | integer | 0..8, 0 = neutral |
| x, y | number | finite, -1..1, normalized schematic coordinates |

The immutable logical event ID is `(session_id, driver_id, sequence)`; no extra
UUID is needed in this slice. A source reconnect must preserve sequences or create
a new session identity. Arrival time is not event order. Source adapters must
explicitly map identifiers, units and coordinate systems.

```json
{"schema_version":1,"session_id":"demo","driver_id":"CAR01","sequence":10,
 "timestamp":1791846000.0,"progress":0.025,"speed_kph":249.7,
 "throttle":0.697,"brake":false,"gear":7,"x":0.9877,"y":0.0939}
```

These are fictional illustrative values. For the simulator, position is derived
from progress around an oval. Production bounds must be reviewed against the
actual feed instead of coercing unfamiliar readings into this contract.

`GET /api/state` returns `session_id`, `source: "simulation"` and `drivers`, an
array of the latest events with a derived integer `position` (1 = leader).
Ties use driver ID for deterministic output. This endpoint contains no official
time gaps, tires or lap classifications. Empty state returns an empty array.

Duplicate and older events do not change current state. Different session events
are rejected by the current state owner. Missing readings are unsupported in v1;
future adapters must introduce an explicit nullable contract rather than invent
zero values. A future schema version needs a migration and compatibility tests.
Before external inputs, add strict field/type parsing, payload-size limits,
received_at timestamps and quarantine for malformed data.
