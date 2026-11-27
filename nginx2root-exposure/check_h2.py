#!/usr/bin/env python3
"""Ask a server what it actually negotiates. Sends one ordinary HEAD request per target.

usage: check_h2.py host[:port] [host[:port] ...]
For each target prints: negotiated HTTP version (via ALPN), the Server header, and the
advice that follows. It sends no exploit traffic. Only point it at servers you operate.
"""
import re, subprocess, sys

def probe(target):
    host, _, port = target.partition(":")
    port = port or "443"
    cmd = ["curl", "-sk", "--max-time", "8", "-o", "/dev/null", "-D", "-", "-I", "--http2",
           "-w", "\nHTTPV=%{http_version}\n", f"https://{host}:{port}/"]
    r = subprocess.run(cmd, capture_output=True, text=True)
    v = re.search(r"HTTPV=(\S+)", r.stdout)
    s = re.search(r"(?im)^server:\s*(.+)$", r.stdout)
    return (v.group(1) if v else "none"), (s.group(1).strip() if s else "(no Server header)")

for t in sys.argv[1:]:
    v, s = probe(t)
    if v == "2":
        advice = "HTTP/2 is negotiated: confirm the package version or the vendor's backport notice, or set `http2 off;` until patched"
    elif v in ("1.1", "1.0"):
        advice = "HTTP/2 is not negotiated on this name"
    else:
        advice = "no TLS answer (check host, port, and SNI name)"
    print(f"{t:30} negotiated={v:5} server={s:22} -> {advice}")
