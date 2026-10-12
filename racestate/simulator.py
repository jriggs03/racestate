"""Deterministic fictional cars on an oval; these are not real F1 readings."""
import math
from queue import Full
import time
from .events import TelemetryEvent

DRIVERS = ("CAR01", "CAR02", "CAR03", "CAR04")


def events_for_tick(sequence, timestamp):
    for index, driver_id in enumerate(DRIVERS):
        progress = sequence * (0.0025 + index * 0.00008) + index * 0.13
        angle = progress * 2 * math.pi
        throttle = 0.65 + 0.3 * math.sin(angle)
        yield TelemetryEvent(
            session_id="demo", driver_id=driver_id, sequence=sequence,
            timestamp=timestamp, progress=progress,
            speed_kph=180 + 100 * throttle, throttle=throttle,
            brake=throttle < 0.4, gear=6 if throttle < 0.6 else 7,
            x=math.cos(angle), y=0.6 * math.sin(angle),
        )


def produce(queue, stop):
    sequence = 0
    while not stop.is_set():
        for event in events_for_tick(sequence, time.time()):
            while not stop.is_set():
                try:
                    queue.put(event, timeout=0.1)
                    break
                except Full:
                    continue  # Backpressure: wait instead of allocating forever.
        sequence += 1
        stop.wait(0.1)
