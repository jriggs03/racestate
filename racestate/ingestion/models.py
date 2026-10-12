"""Pure OpenF1 normalization; no network or storage calls."""
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import hashlib
import json
import math
from typing import Optional, Union


def canonical_json(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def utc_timestamp(value):
    if not isinstance(value, str):
        raise ValueError("date must be an ISO timestamp")
    date = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if date.tzinfo is None:
        raise ValueError("date must include a timezone")
    return date.astimezone(timezone.utc).isoformat(timespec="microseconds")


def integer(record, name, minimum, maximum=None):
    value = record.get(name)
    if type(value) is not int or value < minimum:
        raise ValueError(name + " must be an integer in range")
    if maximum is not None and value > maximum:
        raise ValueError(name + " is out of range")
    return value


def number(record, name, minimum, maximum):
    value = record.get(name)
    if type(value) not in (int, float) or not math.isfinite(value):
        raise ValueError(name + " must be finite")
    if not minimum <= value <= maximum:
        raise ValueError(name + " is out of range")
    return float(value)


@dataclass(frozen=True)
class CarData:
    speed_kph: float
    throttle_fraction: float
    brake: bool
    gear: int
    rpm: int
    drs_code: int  # Preserve the source code; some meanings are uncertain.


@dataclass(frozen=True)
class PositionData:
    position: int


@dataclass(frozen=True)
class SourceEvent:
    event_id: str
    event_type: str
    session_key: int
    driver_number: int
    occurred_at: str
    payload: Union[CarData, PositionData]
    source: str = "openf1"
    schema_version: int = 1
    source_sequence: Optional[int] = None  # OpenF1 REST supplies no sequence.

    def to_dict(self):
        return asdict(self)


def normalize(endpoint: str, record: dict) -> SourceEvent:
    session = integer(record, "session_key", 1)
    driver = integer(record, "driver_number", 1)
    occurred_at = utc_timestamp(record.get("date"))
    if endpoint == "car_data":
        brake = integer(record, "brake", 0, 100)
        if brake not in (0, 100):
            raise ValueError("brake must be 0 or 100")
        payload = CarData(
            speed_kph=number(record, "speed", 0, 500),
            throttle_fraction=number(record, "throttle", 0, 100) / 100,
            brake=brake == 100,
            gear=integer(record, "n_gear", 0, 8),
            rpm=integer(record, "rpm", 0),
            drs_code=integer(record, "drs", 0),
        )
    elif endpoint == "position":
        payload = PositionData(position=integer(record, "position", 1))
    else:
        raise ValueError("supported endpoints: car_data, position")
    # Hash normalized content, not arrival time or Python's randomized hash().
    # A corrected reading is a new event; an identical replay has the same ID.
    content = {"source": "openf1", "schema_version": 1, "event_type": endpoint,
               "session_key": session, "driver_number": driver,
               "occurred_at": occurred_at, "payload": asdict(payload)}
    event_id = hashlib.sha256(canonical_json(content).encode("utf-8")).hexdigest()
    return SourceEvent(event_id, endpoint, session, driver, occurred_at, payload)
