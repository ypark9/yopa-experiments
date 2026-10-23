#!/usr/bin/env python3
"""Minimal PEP 691 simple index with upload-time for local wheels."""
from __future__ import annotations
import hashlib, json, mimetypes
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parents[1]
FIX = ROOT / "fixtures"
HOST, PORT = "127.0.0.1", 8765
PKG = "supplydemo"

def files():
    out = []
    for whl in sorted(FIX.glob(f"{PKG}-*-py3-none-any.whl")):
        ver = whl.name.split("-")[1]
        upload = (FIX / f"{PKG}-{ver}.upload-time").read_text().strip()
        data = whl.read_bytes()
        sha = hashlib.sha256(data).hexdigest()
        out.append({
            "filename": whl.name,
            "url": f"http://{HOST}:{PORT}/files/{whl.name}",
            "hashes": {"sha256": sha},
            "size": len(data),
            "upload-time": upload,
            "requires-python": None,
            "yanked": False,
            "path": whl,
            "version": ver,
        })
    return out

class H(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass
    def _json(self, obj, code=200):
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/vnd.pypi.simple.v1+json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)
    def do_HEAD(self):
        path = unquote(self.path.split("?", 1)[0])
        if path.startswith("/files/"):
            name = path[len("/files/"):]
            whl = FIX / name
            if not whl.is_file() or ".." in name:
                self.send_error(404); return
            self.send_response(200)
            self.send_header("Content-Type", "application/zip")
            self.send_header("Content-Length", str(whl.stat().st_size))
            self.end_headers()
            return
        self.send_error(404)
    def do_GET(self):
        path = unquote(self.path.split("?", 1)[0])
        if path in ("/simple/", "/simple"):
            self._json({"meta": {"api-version": "1.1"}, "projects": [{"name": PKG}]})
            return
        if path in (f"/simple/{PKG}/", f"/simple/{PKG}"):
            fs = files()
            self._json({
                "meta": {"api-version": "1.1"},
                "name": PKG,
                "files": [{k: f[k] for k in ("filename","url","hashes","size","upload-time","requires-python","yanked")} for f in fs],
                "versions": [f["version"] for f in fs],
            })
            return
        if path.startswith("/files/"):
            name = path[len("/files/"):]
            whl = FIX / name
            if not whl.is_file() or ".." in name:
                self.send_error(404); return
            data = whl.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "application/zip")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
            return
        # HTML fallback for older clients
        if path.startswith("/simple/") and path.rstrip("/").endswith(PKG):
            fs = files()
            links = "".join(
                f'<a href="{f["url"]}#sha256={f["hashes"]["sha256"]}">{f["filename"]}</a><br>\n'
                for f in fs)
            body = f"<!doctype html><html><body>{links}</body></html>".encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        self.send_error(404)

if __name__ == "__main__":
    httpd = ThreadingHTTPServer((HOST, PORT), H)
    print(f"INDEX http://{HOST}:{PORT}/simple/{PKG}/", flush=True)
    httpd.serve_forever()
