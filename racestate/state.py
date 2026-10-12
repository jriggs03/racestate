"""One writer updates state; HTTP threads read independent snapshots."""
from threading import Lock


class RaceState:
    def __init__(self, session_id):
        self.session_id = session_id
        self._drivers = {}
        self._lock = Lock()

    def apply(self, event):
        if event.session_id != self.session_id:
            return False
        with self._lock:
            previous = self._drivers.get(event.driver_id)
            if previous is not None and event.sequence <= previous.sequence:
                return False  # Duplicate or late delivery cannot roll state back.
            self._drivers[event.driver_id] = event
            return True

    def snapshot(self):
        with self._lock:
            drivers = [event.to_dict() for event in self._drivers.values()]
        drivers.sort(key=lambda driver: (-driver["progress"], driver["driver_id"]))
        for position, driver in enumerate(drivers, start=1):
            driver["position"] = position
        return {"session_id": self.session_id, "source": "simulation", "drivers": drivers}
