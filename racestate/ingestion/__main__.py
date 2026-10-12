"""Run with python3 -m racestate.ingestion --help."""
import argparse
from datetime import datetime
import json
import sys

from .archive import LocalArchive, S3Archive, drain_archives
from .config import Config
from .log import SQLiteEventLog
from .models import utc_timestamp
from .openf1 import OpenF1Client
from .pipeline import ingest_batch


def positive_integer(text):
    value = int(text)
    if value < 1:
        raise argparse.ArgumentTypeError("must be positive")
    return value


def main():
    parser = argparse.ArgumentParser(description="RaceState phase 1 ingestion and replay")
    commands = parser.add_subparsers(dest="command", required=True)
    ingest = commands.add_parser("ingest", help="fetch one bounded time window")
    ingest.add_argument("--session", type=positive_integer, required=True)
    ingest.add_argument("--endpoint", choices=("car_data", "position"), default="car_data")
    ingest.add_argument("--start", required=True, help="ISO timestamp with timezone")
    ingest.add_argument("--end", required=True, help="exclusive ISO timestamp with timezone")
    ingest.add_argument("--driver", type=positive_integer)
    archive = commands.add_parser("archive", help="drain pending raw copies separately")
    archive.add_argument("--target", choices=("local", "s3"), default="local")
    read = commands.add_parser("read", help="print log entries as JSON lines")
    read.add_argument("--after", type=int, default=0)
    read.add_argument("--limit", type=int, default=100)
    args = parser.parse_args()
    config = Config.from_environment()
    log = SQLiteEventLog(config.log_path)
    try:
        if args.command == "ingest":
            start, end = utc_timestamp(args.start), utc_timestamp(args.end)
            duration = (datetime.fromisoformat(end) - datetime.fromisoformat(start)).total_seconds()
            if not 0 < duration <= 300:
                raise ValueError("use a positive window of at most five minutes")
            raw, records = OpenF1Client(config.openf1_token).fetch(
                args.endpoint, args.session, start, end, args.driver)
            count = ingest_batch(log, args.endpoint, args.session, raw, records)
            print("Committed {} new events; raw archive queued.".format(count))
        elif args.command == "archive":
            if args.target == "s3":
                if not config.s3_bucket:
                    raise ValueError("set RACESTATE_S3_BUCKET before using --target s3")
                destination = S3Archive(config.s3_bucket)
            else:
                destination = LocalArchive(config.archive_dir)
            print("Archived {} raw batches.".format(drain_archives(log, destination)))
        else:
            for entry in log.read_after(args.after, args.limit):
                print(json.dumps({"offset": entry.offset, "event": entry.event}))
    finally:
        log.close()


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError, ImportError) as error:
        print("Ingestion failed: " + str(error), file=sys.stderr)
        sys.exit(1)
