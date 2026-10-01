"""Small dev server for the weather frontend.

Serves the files in this folder and forwards `/weather` to the FastAPI backend.
The proxy means the browser only ever talks to this one origin, so the backend
needs no CORS configuration and stays unmodified.

Run:  python frontend/server.py
Then: open http://localhost:5500
"""

from __future__ import annotations

import argparse
import json
import os
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

FRONTEND_DIR = Path(__file__).parent
DEFAULT_BACKEND = "http://127.0.0.1:8000"
BACKEND_URL = os.environ.get("BACKEND_URL", DEFAULT_BACKEND)


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, directory=str(FRONTEND_DIR), **kwargs)

    def do_GET(self) -> None:
        if urlsplit(self.path).path == "/weather":
            self.forward_weather()
        else:
            super().do_GET()

    def forward_weather(self) -> None:
        try:
            with urlopen(Request(f"{BACKEND_URL}{self.path}", method="GET"), timeout=15) as reply:
                self.send_json_reply(reply.status, reply.read())
        except HTTPError as error:
            self.send_json_reply(error.code, error.read())
        except URLError:
            self.send_json(
                502,
                {
                    "detail": f"Cannot reach the backend at {BACKEND_URL}. "
                    "Start it with: uvicorn main:app"
                },
            )

    def send_json_reply(self, status: int, body: bytes) -> None:
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def send_json(self, status: int, payload: dict) -> None:
        self.send_json_reply(status, json.dumps(payload).encode())


def main() -> None:
    global BACKEND_URL

    parser = argparse.ArgumentParser(description="Serve the weather frontend.")
    parser.add_argument("--port", type=int, default=5500, help="Port for this dev server")
    parser.add_argument("--backend", default=BACKEND_URL, help="Base URL of the FastAPI backend")
    args = parser.parse_args()

    BACKEND_URL = args.backend

    server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    print(f"Frontend:  http://localhost:{args.port}")
    print(f"Backend:   {BACKEND_URL}")
    print("Press Ctrl+C to stop.")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()