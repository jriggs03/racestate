"""Local demo server. Production hosting belongs to a later milestone."""
import json
import os
from pathlib import Path
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from queue import Queue
from threading import Event, Thread
from .simulator import produce
from .state import RaceState
from .worker import consume

WEB = Path(__file__).resolve().parent.parent / "web"


def make_handler(state):
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            path = self.path.split("?", 1)[0]
            if path == "/api/state":
                body = json.dumps(state.snapshot()).encode()
                content_type = "application/json"
            elif path == "/health":
                body = b'{"status":"ok","source":"simulation"}'
                content_type = "application/json"
            elif path in ("/", "/app.js", "/style.css"):
                filename = "index.html" if path == "/" else path[1:]
                body = (WEB / filename).read_bytes()
                content_type = {"index.html": "text/html", "app.js": "text/javascript",
                                "style.css": "text/css"}[filename]
            else:
                self.send_error(404)
                return
            self.send_response(200)
            self.send_header("Content-Type", content_type + "; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, format, *args):
            pass  # Avoid five access-log lines per second during the demo.
    return Handler


def main():
    state = RaceState("demo")
    queue = Queue(maxsize=1000)
    stop = Event()
    # Bind before starting background threads so a busy port fails cleanly.
    server = ThreadingHTTPServer(
        (os.getenv("HOST", "127.0.0.1"), int(os.getenv("PORT", "8000"))),
        make_handler(state),
    )
    producer = Thread(target=produce, args=(queue, stop), name="simulator")
    worker = Thread(target=consume, args=(queue, state, stop), name="state-worker")
    worker.start()
    producer.start()
    print("RaceState simulation: http://%s:%s" % server.server_address, flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        stop.set()
        producer.join()
        worker.join()
        server.server_close()


if __name__ == "__main__":
    main()
