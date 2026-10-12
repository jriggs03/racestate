"""Validate a whole batch before committing it; replay is safe."""
import hashlib
from .models import normalize


def ingest_batch(log, endpoint, session, raw_body, records):
    events = [normalize(endpoint, record) for record in records]
    if any(event.session_key != session for event in events):
        raise ValueError("response contains a different session")
    # REST response order is not promised. Sort within a batch for repeatability.
    events.sort(key=lambda event: (event.occurred_at, event.driver_number, event.event_id))
    digest = hashlib.sha256(raw_body).hexdigest()
    key = "openf1/session={}/{}/{}.json".format(session, endpoint, digest)
    return log.append_batch(events, raw_body, key)
