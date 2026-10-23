#!/usr/bin/env python3
"""Fetch hostname-token and path-token URLs via the local DNS logger; write comparison."""
from __future__ import annotations
import os, socket, subprocess, time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RES = ROOT / "results"
RES.mkdir(exist_ok=True)
LOG = RES / "dns-queries.log"
DNS = ("127.0.0.1", 5355)

# Force resolver to our logger for these names via /etc/hosts is NOT used;
# instead we resolve manually then curl --resolve.

TITLE = "q3-budget-review"
ID = "4d7a19e2"
HOST_A = f"{TITLE}-{ID}.share.test"          # title+id in hostname
HOST_B = "share.test"                        # bare host
PATH_B = f"/s/{TITLE}/{ID}"                  # secret in path

def dns_query(name: str):
    # Build a minimal DNS query and send to logger
    def enc(n):
        o=b""
        for lab in n.split("."):
            b=lab.encode(); o+=bytes([len(b)])+b
        return o+b"\x00"
    req = b"\x12\x34\x01\x00\x00\x01\x00\x00\x00\x00\x00\x00" + enc(name) + b"\x00\x01\x00\x01"
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.settimeout(2)
    s.sendto(req, DNS)
    s.recvfrom(4096)
    s.close()

def curl(host, path="/"):
    cmd = [
        "curl", "-sS", "--max-time", "5",
        "--resolve", f"{host}:8766:127.0.0.1",
        f"http://{host}:8766{path}",
    ]
    # Also perform a DNS lookup the way a browser would (to our logger)
    dns_query(host)
    p = subprocess.run(cmd, capture_output=True, text=True)
    return p.returncode, p.stdout.strip(), p.stderr.strip(), " ".join(cmd)

time.sleep(0.3)
LOG.write_text("")
# A: hostname scheme
ca = curl(HOST_A, "/")
# B: path scheme
cb = curl(HOST_B, PATH_B)
time.sleep(0.2)
queries = LOG.read_text().strip().splitlines() if LOG.exists() else []
qnames = [line.split("\t")[1] for line in queries if "\t" in line]

md = []
md.append("# Hostname token vs path token — local DNS log\n\n")
md.append(f"Scheme A URL: `http://{HOST_A}:8766/`\n\n")
md.append(f"Scheme B URL: `http://{HOST_B}:8766{PATH_B}`\n\n")
md.append("## DNS queries observed\n\n")
for line in queries:
    md.append(f"- `{line}`\n")
md.append("\n## Outcome\n\n")
a_leaked = any(TITLE in q for q in qnames)
b_leaked = any(TITLE in q for q in qnames if q == HOST_B or q.startswith("share."))
# tighter: title appears in a query name
title_in_dns = [q for q in qnames if TITLE in q]
md.append(f"- Queries containing the conversation title `{TITLE}`: {title_in_dns or 'none'}\n")
md.append(f"- Scheme A (title in hostname) published title to DNS: **{'yes' if HOST_A in qnames else 'no'}**\n")
md.append(f"- Scheme B (title in path only) published title to DNS: **{'yes' if any(TITLE in q and q != HOST_A for q in qnames) else 'no'}**\n")
md.append(f"- Scheme B host query was: `{[q for q in qnames if q == HOST_B]}`\n")
md.append("\n## HTTP checks\n\n")
md.append(f"- A: exit={ca[0]} body=`{ca[1]}`\n")
md.append(f"- B: exit={cb[0]} body=`{cb[1]}`\n")
md.append("\n## Note\n\n")
md.append("This is a local model of the leak channel (DNS query logging). ")
md.append("It does not query commercial passive DNS and does not touch Meta Muse hosts.\n")
(RES / "comparison.md").write_text("".join(md))
(RES / "comparison.json").write_text(
    __import__("json").dumps({
        "host_a": HOST_A, "host_b": HOST_B, "path_b": PATH_B,
        "queries": qnames,
        "title_in_hostname_query": HOST_A in qnames,
        "title_in_any_query": bool(title_in_dns),
        "path_scheme_host_queries": [q for q in qnames if q == HOST_B],
        "curl_a": {"code": ca[0], "body": ca[1]},
        "curl_b": {"code": cb[0], "body": cb[1]},
    }, indent=2) + "\n"
)
print("".join(md))
