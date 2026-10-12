"""The shared telemetry contract. No networking or storage here."""
from dataclasses import dataclass, asdict
import math


@dataclass(frozen=True)
class TelemetryEvent:
    session_id: str
    driver_id: str
    sequence: int
    timestamp: float  # Unix seconds, UTC
    progress: float  # Completed laps plus fraction of current lap
    speed_kph: float
    throttle: float  # 0..1
    brake: bool
    gear: int
    x: float  # Normalized schematic coordinates, -1..1
    y: float
    schema_version: int = 1

    def __post_init__(self):
        if self.schema_version != 1:
            raise ValueError("unsupported schema version")
        if not self.session_id or not self.driver_id:
            raise ValueError("session and driver are required")
        if type(self.sequence) is not int or self.sequence < 0:
            raise ValueError("sequence must be a nonnegative integer")
        for name in ("timestamp", "progress", "speed_kph", "throttle", "x", "y"):
            value = getattr(self, name)
            if type(value) not in (int, float) or not math.isfinite(value):
                raise ValueError(name + " must be a finite number")
        if self.timestamp < 0 or self.progress < 0 or not 0 <= self.speed_kph <= 400:
            raise ValueError("invalid time, progress or speed")
        if not 0 <= self.throttle <= 1 or type(self.brake) is not bool:
            raise ValueError("invalid throttle or brake")
        if type(self.gear) is not int or not 0 <= self.gear <= 8:
            raise ValueError("gear must be an integer from 0 to 8")
        if not -1 <= self.x <= 1 or not -1 <= self.y <= 1:
            raise ValueError("coordinates must be normalized")

    def to_dict(self):
        return asdict(self)
