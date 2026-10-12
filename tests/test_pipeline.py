import math
from dataclasses import replace
from http.server import ThreadingHTTPServer
import json
from queue import Queue
from threading import Event, Thread
import unittest
from urllib.request import urlopen
from racestate.simulator import events_for_tick
from racestate.state import RaceState
from racestate.worker import consume
from racestate.server import make_handler


class PipelineTests(unittest.TestCase):
    def setUp(self):
        self.event = next(events_for_tick(10, 1000.0))

    def test_invalid_readings_rejected(self):
        for changes in ({"speed_kph": math.nan}, {"throttle": 2}, {"x": 2},
                        {"gear": 3.5}, {"sequence": -1}, {"schema_version": 2}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                replace(self.event, **changes)

    def test_duplicate_late_and_other_session_ignored(self):
        state = RaceState("demo")
        self.assertTrue(state.apply(self.event))
        self.assertFalse(state.apply(self.event))
        self.assertFalse(state.apply(replace(self.event, sequence=9)))
        self.assertFalse(state.apply(replace(self.event, session_id="other")))
        self.assertEqual(state.snapshot()["drivers"][0]["sequence"], 10)

    def test_order_and_snapshot_isolation(self):
        state = RaceState("demo")
        for event in events_for_tick(10, 1000):
            state.apply(event)
        snapshot = state.snapshot()
        self.assertEqual(snapshot["drivers"][0]["driver_id"], "CAR04")
        snapshot["drivers"][0]["sequence"] = -1
        self.assertEqual(state.snapshot()["drivers"][0]["sequence"], 10)

    def test_queue_worker_and_http(self):
        queue = Queue(maxsize=10)
        stop = Event()
        state = RaceState("demo")
        for event in events_for_tick(10, 1000):
            queue.put(event)
        stop.set()  # Shutdown must still drain already queued events.
        worker = Thread(target=consume, args=(queue, state, stop))
        worker.start()
        worker.join(timeout=2)
        self.assertFalse(worker.is_alive())
        self.assertEqual(queue.unfinished_tasks, 0)
        server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(state))
        thread = Thread(target=server.serve_forever)
        thread.start()
        try:
            base = "http://127.0.0.1:" + str(server.server_port)
            with urlopen(base + "/api/state", timeout=2) as response:
                snapshot = json.load(response)
            self.assertEqual(len(snapshot["drivers"]), 4)
            with urlopen(base + "/", timeout=2) as response:
                self.assertIn(b"SIMULATED SESSION", response.read())
        finally:
            server.shutdown()
            thread.join()
            server.server_close()


if __name__ == "__main__":
    unittest.main()
