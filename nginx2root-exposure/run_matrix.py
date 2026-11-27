#!/usr/bin/env python3
"""nginx2root exposure checks that send NO exploit traffic.

Part 1: for each nginx binary, start a plain TLS+HTTP/2 server and record the banner,
        whether h2 is negotiated, and what the packaging changelog says about CVE-2026-123007.
Part 2: config matrix: compare a naive `grep http2` verdict with the protocol that
        a real client negotiates (ALPN via curl, or prior knowledge for cleartext).
Everything binds to 127.0.0.1 and uses a throwaway self-signed certificate.
"""
import os, re, subprocess, sys, tempfile, time, json, gzip, shutil, glob, pathlib

HERE = pathlib.Path(__file__).resolve().parent
PKG = pathlib.Path(os.environ.get("NGINX_PKG_DIR", "/workspace/nginx-exp/x"))
CERT, KEY = HERE / "c.pem", HERE / "k.pem"
OUT = HERE / "results"
OUT.mkdir(exist_ok=True)

def make_cert():
    if CERT.exists() and KEY.exists():
        return
    subprocess.run(["openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes", "-keyout", str(KEY),
                    "-out", str(CERT), "-days", "2", "-subj", "/CN=localhost",
                    "-addext", "subjectAltName=DNS:localhost,DNS:a.test,DNS:b.test"],
                   check=True, capture_output=True)

def conf_text(body, port_dir):
    return f"""daemon off; pid {port_dir}/nginx.pid; error_log {port_dir}/error.log warn;
worker_processes 1;
events {{ worker_connections 64; }}
http {{
  access_log off; client_body_temp_path {port_dir}/cb; proxy_temp_path {port_dir}/pt;
  fastcgi_temp_path {port_dir}/fc; uwsgi_temp_path {port_dir}/uw; scgi_temp_path {port_dir}/sc;
  ssl_certificate {CERT}; ssl_certificate_key {KEY};
{body}
}}
"""

class Server:
    def __init__(self, binary, body):
        self.dir = pathlib.Path(tempfile.mkdtemp(prefix="ngx-"))
        self.conf = self.dir / "nginx.conf"
        self.conf.write_text(conf_text(body, self.dir))
        self.binary = str(binary)
        self.p = None
    def __enter__(self):
        t = subprocess.run([self.binary, "-t", "-c", str(self.conf), "-p", str(self.dir)], capture_output=True, text=True)
        self.test = (t.stdout + t.stderr).strip()
        if t.returncode != 0:
            raise RuntimeError("config test failed: " + self.test)
        self.p = subprocess.Popen([self.binary, "-c", str(self.conf), "-p", str(self.dir)],
                                  stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        time.sleep(0.4)
        return self
    def dump(self):
        r = subprocess.run([self.binary, "-T", "-c", str(self.conf), "-p", str(self.dir)], capture_output=True, text=True)
        return r.stdout
    def __exit__(self, *a):
        if self.p:
            self.p.terminate()
            try: self.p.wait(5)
            except Exception: self.p.kill()
        shutil.rmtree(self.dir, ignore_errors=True)

def probe(url, extra=()):
    """Return (negotiated HTTP version, Server header) using curl."""
    cmd = ["curl", "-sk", "--max-time", "5", "-o", "/dev/null", "-D", "-", "-w", "\nHTTPV=%{http_version}\n", *extra, url]
    r = subprocess.run(cmd, capture_output=True, text=True)
    m = re.search(r"HTTPV=(\S+)", r.stdout)
    s = re.search(r"(?im)^server:\s*(.+)$", r.stdout)
    return (m.group(1) if m else "none"), (s.group(1).strip() if s else "(no Server header)")

def naive_grep_verdict(dump):
    """What a quick `grep` on the config says. Deliberately simple: any non-comment line that mentions http2."""
    lines = [l.strip() for l in dump.splitlines() if not l.strip().startswith("#")]
    hits = [l for l in lines if re.search(r"\bhttp2\b", l)]
    return "HTTP/2 on" if hits else "no http2", hits

def grep_listen_only(dump):
    """The other common rule: only look at `listen ... http2`."""
    lines = [l.strip() for l in dump.splitlines() if not l.strip().startswith("#")]
    hits = [l for l in lines if re.match(r"listen\b.*\bhttp2\b", l)]
    return "HTTP/2 on" if hits else "no http2", hits

def changelog_mentions(pkgdir, cve):
    for f in glob.glob(str(pkgdir / "usr/share/doc/nginx/changelog.Debian.gz")):
        t = gzip.open(f, "rt", errors="replace").read()
        m = re.search(r"nginx \(([^)]+)\)[^\n]*\n(.*?)(?=\nnginx \(|\Z)", t, re.S)
        blocks = re.findall(r"(nginx \(([^)]+)\)[^\n]*\n.*?)(?=\nnginx \(|\Z)", t, re.S)
        for b, ver in blocks:
            if cve in b:
                return ver
    return None

SIMPLE = """
  server { listen 127.0.0.1:%d ssl; http2 on; server_name localhost; location / { return 200 "ok\\n"; } }
"""

def part1():
    rows = []
    port = 18443
    for d in sorted(PKG.glob("nginx_*")):
        binary = d / "usr/sbin/nginx"
        ver = subprocess.run([str(binary), "-v"], capture_output=True, text=True)
        banner_ver = re.search(r"nginx/(\S+)", ver.stdout + ver.stderr).group(1)
        with Server(binary, SIMPLE % port) as s:
            hv, sh = probe(f"https://127.0.0.1:{port}/", ["--http2"])
        fixed_in = changelog_mentions(d, "CVE-2026-123007")
        rows.append({"package": d.name.replace("_amd64", ""), "banner_version": banner_ver, "server_header": sh,
                     "negotiated": hv, "packaging_changelog_lists_CVE-2026-123007_patch": fixed_in})
    return rows

def vtuple(v):
    return tuple(int(x) for x in re.findall(r"\d+", v.split("-")[0]))

def naive_banner_verdict(banner_ver):
    """Upstream rule from nginx.org: affected 1.9.5-1.30.6 and 1.31.0-1.31.8; fixed 1.30.7+/1.31.9+."""
    v = vtuple(banner_ver)
    if v[:2] == (1, 31):
        return "vulnerable" if v[2] <= 8 else "fixed"
    return "vulnerable" if v <= (1, 30, 6) else "fixed"

CASES = [
 ("A modern: ssl + `http2 on;` in server", "server {\n    listen 127.0.0.1:%d ssl;\n    http2 on;\n    return 200 'ok';\n  }", "alpn"),
 ("B legacy: `listen ... ssl http2;`", "server {\n    listen 127.0.0.1:%d ssl http2;\n    return 200 'ok';\n  }", "alpn"),
 ("C ssl only, no http2 directive", "server {\n    listen 127.0.0.1:%d ssl;\n    return 200 'ok';\n  }", "alpn"),
 ("D `http2 on;` set once at http level, plain `listen ... ssl;`", "http2 on;\n  server {\n    listen 127.0.0.1:%d ssl;\n    return 200 'ok';\n  }", "alpn"),
 ("E `http2 on;` at http level, `http2 off;` in the server", "http2 on;\n  server {\n    listen 127.0.0.1:%d ssl;\n    http2 off;\n    return 200 'ok';\n  }", "alpn"),
 ("F `# http2 on;` only as a comment", "server {\n    listen 127.0.0.1:%d ssl;\n    # http2 on;\n    return 200 'ok';\n  }", "alpn"),
 ("G cleartext `listen ... http2;` (no TLS)", "server {\n    listen 127.0.0.1:%d http2;\n    return 200 'ok';\n  }", "h2c"),
 ("H cleartext, no http2", "server {\n    listen 127.0.0.1:%d;\n    return 200 'ok';\n  }", "h2c"),
]

def part2(binary):
    rows = []
    port = 18500
    for name, body, mode in CASES:
        port += 1
        with Server(binary, "  " + (body % port)) as s:
            dump = s.dump()
            if mode == "alpn":
                hv, _ = probe(f"https://127.0.0.1:{port}/", ["--http2"])
            else:
                hv, _ = probe(f"http://127.0.0.1:{port}/", ["--http2-prior-knowledge"])
        g1, h1 = naive_grep_verdict(dump)
        g2, h2 = grep_listen_only(dump)
        live = "HTTP/2 on" if hv == "2" else "no http2"
        rows.append({"case": name, "grep_any_http2": g1, "grep_listen_line_only": g2, "live_negotiated": hv, "live_verdict": live,
                     "grep_any_correct": g1 == live, "grep_listen_correct": g2 == live})
    return rows

def part3(binary):
    """Two server blocks on one TLS port: does the per-server `http2` setting follow SNI?"""
    port = 18600
    body = f"""
  server {{ listen 127.0.0.1:{port} ssl default_server; server_name b.test; http2 off; return 200 "b"; }}
  server {{ listen 127.0.0.1:{port} ssl; server_name a.test; http2 on; return 200 "a"; }}
"""
    out = []
    with Server(binary, body) as s:
        for host in ("a.test", "b.test", "no-sni"):
            extra = ["--http2"]
            if host != "no-sni":
                extra += ["--resolve", f"{host}:{port}:127.0.0.1"]
                url = f"https://{host}:{port}/"
            else:
                url = f"https://127.0.0.1:{port}/"
            hv, _ = probe(url, extra)
            out.append({"requested_host": host, "negotiated": hv})
    return out

def main():
    make_cert()
    p1 = part1()
    for r in p1:
        r["upstream_rule_from_banner"] = naive_banner_verdict(r["banner_version"])
    b130 = PKG / "nginx_1.30.7-1~trixie_amd64/usr/sbin/nginx"
    p2 = part2(b130)
    p3 = part3(b130)
    res = {"part1_versions": p1, "part2_config_matrix": p2, "part3_shared_port_sni": p3,
           "curl": subprocess.run(["curl", "--version"], capture_output=True, text=True).stdout.splitlines()[0]}
    (OUT / "results.json").write_text(json.dumps(res, indent=2))
    print(json.dumps(res, indent=2))

if __name__ == "__main__":
    main()
