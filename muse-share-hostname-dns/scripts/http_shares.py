#!/usr/bin/env python3
"""Two share URL schemes on 127.0.0.1: hostname-token vs path-token."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HOST, PORT = "127.0.0.1", 8766

class H(BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def do_GET(self):
        host = self.headers.get("Host", "").split(":")[0].lower()
        body = f"ok host={host} path={self.path}\n".encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/plain")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

if __name__ == "__main__":
    print(f"HTTP shares on {HOST}:{PORT}", flush=True)
    ThreadingHTTPServer((HOST, PORT), H).serve_forever()
