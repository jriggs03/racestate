"""Offline boundary tests; no AWS account or OpenF1 subscription needed."""
from copy import deepcopy
from io import BytesIO
import json
import os
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest
from urllib.error import HTTPError
from unittest.mock import Mock, patch

from racestate.ingestion.archive import LocalArchive, S3Archive, drain_archives
from racestate.ingestion.log import SQLiteEventLog
from racestate.ingestion.models import normalize
from racestate.ingestion.openf1 import OpenF1Client
from racestate.ingestion.pipeline import ingest_batch


CAR = {"session_key": 9159, "meeting_key": 1219, "driver_number": 55,
       "date": "2023-09-15T13:08:19.923000+00:00", "speed": 315,
       "throttle": 99, "brake": 0, "n_gear": 8, "rpm": 11141, "drs": 12}


class NormalizationTests(unittest.TestCase):
    def test_id_stable_across_key_order_timezone_and_process(self):
        event = normalize("car_data", CAR)
        reordered = dict(reversed(list(CAR.items())))
        reordered["date"] = "2023-09-15T06:08:19.923-07:00"
        self.assertEqual(event.event_id, normalize("car_data", reordered).event_id)
        code = "from racestate.ingestion.models import normalize; import json; print(normalize('car_data', json.loads(input())).event_id)"
        result = subprocess.run([sys.executable, "-c", code], input=json.dumps(CAR),
                                text=True, capture_output=True, check=True)
        self.assertEqual(result.stdout.strip(), event.event_id)
        self.assertIsNone(event.source_sequence)
        self.assertEqual(event.payload.throttle_fraction, .99)
        self.assertFalse(event.payload.brake)

    def test_changed_content_and_driver_have_distinct_ids(self):
        original = normalize("car_data", CAR).event_id
        for change in ({"speed": 314}, {"driver_number": 44}, {"session_key": 9160}):
            self.assertNotEqual(original, normalize("car_data", dict(CAR, **change)).event_id)

    def test_invalid_data_rejected(self):
        for change in ({"speed": float("nan")}, {"speed": True}, {"throttle": 101},
                       {"brake": 50}, {"n_gear": 9}, {"rpm": None},
                       {"date": "2023-09-15T13:08:19"}, {"driver_number": True}):
            with self.subTest(change=change), self.assertRaises(ValueError):
                normalize("car_data", dict(CAR, **change))
        missing = deepcopy(CAR)
        del missing["speed"]
        with self.assertRaises(ValueError):
            normalize("car_data", missing)

    def test_position_is_separate_from_telemetry(self):
        event = normalize("position", dict(CAR, position=2))
        self.assertEqual(event.to_dict()["payload"], {"position": 2})
        self.assertNotEqual(event.event_id, normalize("car_data", CAR).event_id)


class DurabilityTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.path = str(Path(self.temp.name) / "events.sqlite3")
        self.log = SQLiteEventLog(self.path)

    def tearDown(self):
        self.log.close()
        self.temp.cleanup()

    def ingest(self, records):
        return ingest_batch(self.log, "car_data", 9159, json.dumps(records).encode(), records)

    def test_restart_duplicate_and_offset_replay(self):
        later = dict(CAR, date="2023-09-15T13:08:20Z")
        self.assertEqual(self.ingest([later, CAR]), 2)
        first = self.log.read_after(0)
        self.assertLess(first[0].event["occurred_at"], first[1].event["occurred_at"])
        self.log.close()
        self.log = SQLiteEventLog(self.path)
        self.assertEqual(self.ingest([CAR, later]), 0)
        self.assertEqual(self.log.read_after(first[0].offset), first[1:])
        self.assertTrue(self.log.pending_archives())
        # Older data remains replayable; offset order is not source-time order.
        older = dict(CAR, date="2023-09-15T13:08:18Z")
        self.ingest([older])
        self.assertLess(self.log.read_after(first[-1].offset)[0].event["occurred_at"],
                        first[0].event["occurred_at"])

    def test_malformed_batch_and_wrong_session_commit_nothing(self):
        for records in ([CAR, dict(CAR, brake=50)], [dict(CAR, session_key=1)]):
            with self.assertRaises(ValueError):
                self.ingest(records)
        self.assertEqual(self.log.read_after(0), [])
        self.assertEqual(self.log.pending_archives(), [])

    def test_transaction_failure_rolls_back_events_and_archive(self):
        class BrokenEvent:
            event_id = "broken"
            def to_dict(self):
                raise ValueError("injected serialization failure")
        with self.assertRaises(ValueError):
            self.log.append_batch([normalize("car_data", CAR), BrokenEvent()], b"[]", "test.json")
        self.assertEqual(self.log.read_after(0), [])
        self.assertEqual(self.log.pending_archives(), [])

    def test_abrupt_exit_preserves_committed_data(self):
        code = """
import json, os, sys
from racestate.ingestion.log import SQLiteEventLog
from racestate.ingestion.pipeline import ingest_batch
record = json.loads(sys.stdin.read())
log = SQLiteEventLog(sys.argv[1])
ingest_batch(log, 'car_data', 9159, json.dumps([record]).encode(), [record])
os._exit(0)
"""
        subprocess.run([sys.executable, "-c", code, self.path], input=json.dumps(CAR),
                       text=True, check=True)
        self.assertEqual(len(self.log.read_after(0)), 1)
        self.assertEqual(len(self.log.pending_archives()), 1)

    def test_archive_failure_retries_after_restart_without_losing_log(self):
        self.ingest([CAR])
        archive = Mock()
        archive.put.side_effect = OSError("AWS unavailable")
        with self.assertRaises(OSError):
            drain_archives(self.log, archive)
        self.log.close()
        self.log = SQLiteEventLog(self.path)
        self.assertEqual(len(self.log.read_after(0)), 1)
        self.assertEqual(len(self.log.pending_archives()), 1)
        key, body = self.log.pending_archives()[0]
        root = Path(self.temp.name) / "raw"
        self.assertEqual(drain_archives(self.log, LocalArchive(root)), 1)
        self.assertEqual((root / key).read_bytes(), body)
        self.assertEqual(drain_archives(self.log, LocalArchive(root)), 0)

    def test_s3_adapter_uses_exact_raw_bytes(self):
        client = Mock()
        S3Archive("my-bucket", client).put("raw/example.json", b'[ {"x": 1} ]')
        client.put_object.assert_called_once_with(
            Bucket="my-bucket", Key="raw/example.json", Body=b'[ {"x": 1} ]',
            ContentType="application/json")


class SourceTests(unittest.TestCase):
    def test_filters_raw_bytes_and_optional_token(self):
        raw = json.dumps([CAR]).encode()
        opener = Mock(return_value=BytesIO(raw))
        body, records = OpenF1Client("test-token", opener=opener).fetch(
            "car_data", 9159, "2023-09-15T13:08:19Z", "2023-09-15T13:08:20Z", 55)
        self.assertEqual(body, raw)
        self.assertEqual(records, [CAR])
        request = opener.call_args[0][0]
        self.assertIn("&date>=2023-09-15T13%3A08%3A19Z", request.full_url)
        self.assertIn("&date<2023-09-15T13%3A08%3A20Z", request.full_url)
        self.assertNotIn("date>==", request.full_url)
        self.assertIn("driver_number=55", request.full_url)
        self.assertEqual(request.get_header("Authorization"), "Bearer test-token")

    def test_temporary_failure_retries_but_auth_error_does_not(self):
        sleep = Mock()
        error = HTTPError("test", 429, "rate limited", {"Retry-After": "3"}, None)
        opener = Mock(side_effect=[error, BytesIO(b"[]")])
        self.assertEqual(OpenF1Client(opener=opener, sleep=sleep).fetch(
            "position", 9159, "start", "end"), (b"[]", []))
        sleep.assert_called_once_with(3)
        opener = Mock(side_effect=HTTPError("test", 401, "unauthorized", {}, None))
        with self.assertRaises(HTTPError):
            OpenF1Client(opener=opener, sleep=sleep).fetch("position", 9159, "start", "end")
        self.assertEqual(opener.call_count, 1)

    def test_retry_exhaustion_and_bad_response(self):
        opener = Mock(side_effect=HTTPError("test", 503, "unavailable", {}, None))
        with self.assertRaises(HTTPError):
            OpenF1Client(opener=opener, sleep=Mock()).fetch("position", 9159, "start", "end")
        self.assertEqual(opener.call_count, 3)
        for body in (b'{}', b'[1]', b'not json'):
            with self.subTest(body=body), self.assertRaises(ValueError):
                OpenF1Client(opener=Mock(return_value=BytesIO(body))).fetch(
                    "position", 9159, "start", "end")


class CommandTests(unittest.TestCase):
    def test_configuration_read_and_missing_s3_bucket(self):
        with TemporaryDirectory() as directory:
            path = str(Path(directory) / "configured.sqlite3")
            env = dict(os.environ, RACESTATE_LOG_PATH=path, RACESTATE_S3_BUCKET="")
            log = SQLiteEventLog(path)
            ingest_batch(log, "car_data", 9159, json.dumps([CAR]).encode(), [CAR])
            log.close()
            result = subprocess.run(
                [sys.executable, "-m", "racestate.ingestion", "read", "--limit", "1"],
                env=env, text=True, capture_output=True, check=True)
            self.assertEqual(json.loads(result.stdout)["event"]["driver_number"], 55)
            result = subprocess.run(
                [sys.executable, "-m", "racestate.ingestion", "archive", "--target", "s3"],
                env=env, text=True, capture_output=True)
            self.assertEqual(result.returncode, 1)
            self.assertIn("set RACESTATE_S3_BUCKET", result.stderr)

    def test_response_size_is_bounded(self):
        with patch("racestate.ingestion.openf1.MAX_RESPONSE_BYTES", 5):
            client = OpenF1Client(opener=Mock(return_value=BytesIO(b"[{},{}]")))
            with self.assertRaisesRegex(ValueError, "response too large"):
                client.fetch("position", 9159, "start", "end")
