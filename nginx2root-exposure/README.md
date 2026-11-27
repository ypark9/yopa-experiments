# nginx2root exposure: what a banner, a config grep, and a live probe each tell you

Date: 2026-11-27. Everything here ran on one Linux box with loopback sockets and a throwaway
self-signed certificate. **No exploit, crash trigger, or malformed HTTP/2 frame was sent.** Cost: none
(local CPU only, no cloud account, no paid service).

Question: CVE-2026-123007 and CVE-2026-123633 are HTTP/2 bugs in nginx (fixed upstream in 1.30.7 and 1.31.9).
How do you tell whether *your* server is exposed, and which quick checks mislead you?

## How to rerun

```bash
# nginx binaries come from the packages' .deb files (extracted with dpkg-deb -x, no install, no root)
NGINX_PKG_DIR=/path/to/extracted/packages python3 run_matrix.py
python3 check_h2.py your-host.example:443      # only against servers you operate
```

`NGINX_PKG_DIR` holds one directory per package (`nginx_<version>_amd64/usr/sbin/nginx`).
The packages used: Debian `1.26.3-3+deb13u11` (trixie-security) and nginx.org `1.30.6`, `1.30.7`, `1.30.8`.

## Result 1: the banner and the packaging changelog disagree on Debian

| Package | `Server` header | h2 negotiated? | Rule "banner vs nginx.org advisory" says | Packaging changelog lists the CVE-2026-123007 patch? |
|---|---|---|---|---|
| Debian 1.26.3-3+deb13u11 | nginx/1.26.3 | yes | vulnerable | yes (in 1.26.3-3+deb13u11) |
| nginx.org 1.30.6 | nginx/1.30.6 | yes | vulnerable | not mentioned (upstream changelogs do not list CVEs) |
| nginx.org 1.30.7 | nginx/1.30.7 | yes | fixed | not mentioned |
| nginx.org 1.30.8 | nginx/1.30.8 | yes | fixed | not mentioned |

Takeaway: a scanner that compares the banner with the upstream fixed version flags the Debian package as vulnerable,
while Debian's own changelog says the fix was backported. The "fixed" column for 1.30.7/1.30.8 and the "vulnerable"
verdicts come from the advisory's version ranges, **not** from testing for the bug.

## Result 2: config checks versus what a client really negotiates

Server: nginx.org 1.30.7. Probe: `curl --http2` (ALPN) for TLS listeners, `curl --http2-prior-knowledge` for cleartext.

| Case | grep: any non-comment line with `http2` | grep: only `listen ... http2` | Live result | Both greps right? |
|---|---|---|---|---|
| A `http2 on;` inside the server | on | off | HTTP/2 | any: yes, listen-only: **no** |
| B legacy `listen ... ssl http2;` | on | on | HTTP/2 | yes |
| C TLS listener, no http2 directive | off | off | HTTP/1.1 | yes |
| D `http2 on;` once at `http` level | on | off | HTTP/2 | any: yes, listen-only: **no** |
| E `http2 on;` at `http`, `http2 off;` in the server | on | off | HTTP/1.1 | any: **no**, listen-only: yes |
| F `# http2 on;` only as a comment | off | off | HTTP/1.1 | yes |
| G cleartext `listen ... http2;` | on | on | HTTP/2 (prior knowledge) | yes |
| H cleartext, no http2 | off | off | not HTTP/2 | yes |

Takeaway: the `listen ... http2` rule misses the modern `http2 on;` syntax (cases A and D), and the "any line" rule is
fooled by an override (case E). The live probe matched the real behavior in all eight cases.

## Result 3: one TLS port, two servers, different `http2` settings

| SNI name sent | Negotiated |
|---|---|
| a.test (server has `http2 on;`) | HTTP/2 |
| b.test (default server, `http2 off;`) | HTTP/1.1 |
| no SNI | HTTP/1.1 (default server's setting) |

Takeaway: HTTP/2 follows the server block that the SNI name selects, so a probe must try every name you serve.

## What this does not show

- It does not show that any package is or is not exploitable; it never sends the triggering traffic.
- Result 1's "fixed" and "vulnerable" labels are copied from nginx.org's advisory ranges and Debian's changelog text.
- `http2 off;` as a stopgap changes how browsers connect (more parallel connections). Its performance cost is **not measured** here,
  because loopback has no round-trip time to expose it.
- Only nginx binaries from the four packages above were run, on one CPU architecture (amd64), with curl 8.14.1.
