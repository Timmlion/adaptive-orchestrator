import argparse
import json
import mimetypes
import signal
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlparse

from boardlib import board_snapshot


class DashboardHandler(BaseHTTPRequestHandler):
    board = Path(".agent-board")

    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/api/board":
            try:
                body = json.dumps(board_snapshot(self.board), allow_nan=False).encode("utf-8")
            except (TypeError, ValueError):
                self._send_json(500, {"error": "Unable to serialize board snapshot"})
                return
            self._send_json(200, body)
            return
        self._serve_static(path)

    def _send_json(self, status, payload):
        body = payload if isinstance(payload, bytes) else json.dumps(payload, allow_nan=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _serve_static(self, request_path):
        relative = "index.html" if request_path in ("", "/") else unquote(request_path).lstrip("/")
        root = self.board / "dashboard"
        candidate = (root / relative).resolve()
        if root.resolve() not in candidate.parents or not candidate.is_file():
            self.send_error(404)
            return
        body = candidate.read_bytes()
        content_type = mimetypes.guess_type(candidate.name)[0] or "application/octet-stream"
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        pass


parser = argparse.ArgumentParser()
parser.add_argument("--board", default=".agent-board")
parser.add_argument("--host", default="127.0.0.1")
parser.add_argument("--port", type=int, default=8765)
args = parser.parse_args()
DashboardHandler.board = Path(args.board)
server = ThreadingHTTPServer((args.host, args.port), DashboardHandler)


def stop_server(_signum, _frame):
    raise KeyboardInterrupt


signal.signal(signal.SIGTERM, stop_server)
print(f"READY {server.server_port}", flush=True)
try:
    server.serve_forever()
except KeyboardInterrupt:
    pass
finally:
    server.server_close()
