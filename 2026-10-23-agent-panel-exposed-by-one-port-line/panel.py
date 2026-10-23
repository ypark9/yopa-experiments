#!/usr/bin/env python3
"""Stand-in for an agent control panel: no auth, like the Cairn server app.
GET /projects returns a fake project list. Nothing here talks to the network
except the socket it listens on."""
import argparse, json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

class H(BaseHTTPRequestHandler):
    def do_GET(self):
        body = json.dumps({"projects": [{"id": 1, "goal": "demo"}]}).encode()
        self.send_response(200 if self.path == "/projects" else 404)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(body)
    def log_message(self, *a):
        pass

ap = argparse.ArgumentParser()
ap.add_argument("--host", default="127.0.0.1")  # same default as `cairn serve`
ap.add_argument("--port", type=int, default=8000)
a = ap.parse_args()
ThreadingHTTPServer((a.host, a.port), H).serve_forever()
