"""One bounded REST query, with bounded retries for temporary failures."""
import json
import time
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

MAX_RESPONSE_BYTES = 20 * 1024 * 1024


class OpenF1Client:
    def __init__(self, token="", timeout=20, opener=urlopen, sleep=time.sleep):
        self.token = token
        self.timeout = timeout
        self.opener = opener
        self.sleep = sleep

    def fetch(self, endpoint, session, start, end, driver=None):
        if endpoint not in ("car_data", "position"):
            raise ValueError("unsupported endpoint")
        filters = {"session_key": session}
        if driver is not None:
            filters["driver_number"] = driver
        headers = {"Accept": "application/json", "User-Agent": "RaceState/phase-1"}
        if self.token:
            headers["Authorization"] = "Bearer " + self.token
        # OpenF1 parses comparison expressions, not ordinary key=value pairs.
        # urlencode({"date>=": start}) adds an extra '=' and breaks that syntax.
        # Encode values only, retaining the documented comparison operators.
        start_value = quote(start.replace("+00:00", "Z"), safe="")
        end_value = quote(end.replace("+00:00", "Z"), safe="")
        query = urlencode(filters) + "&date>=" + start_value + "&date<" + end_value
        request = Request("https://api.openf1.org/v1/" + endpoint + "?" + query,
                          headers=headers)
        for attempt in range(3):
            try:
                with self.opener(request, timeout=self.timeout) as response:
                    body = response.read(MAX_RESPONSE_BYTES + 1)
                if len(body) > MAX_RESPONSE_BYTES:
                    raise ValueError("response too large; use a smaller time window")
                records = json.loads(body)
                if not isinstance(records, list) or not all(isinstance(r, dict) for r in records):
                    raise ValueError("OpenF1 response must be an array of objects")
                return body, records
            except HTTPError as error:
                if error.code != 429 and error.code < 500:
                    raise
                if attempt == 2:
                    raise
                # Respect numeric Retry-After, capped so a command cannot hang forever.
                retry_after = error.headers.get("Retry-After", "")
                delay = min(60, float(retry_after)) if retry_after.isdigit() else 2 ** (attempt + 1)
            except (URLError, TimeoutError):
                if attempt == 2:
                    raise
                delay = 2 ** (attempt + 1)
            self.sleep(delay)
