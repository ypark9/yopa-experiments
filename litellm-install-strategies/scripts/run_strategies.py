#!/usr/bin/env python3
"""Run install strategies against the local index. Never touches real PyPI for supplydemo."""
from __future__ import annotations
import json, os, shutil, subprocess, sys, tempfile, time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIX = ROOT / "fixtures"
RES = ROOT / "results"
RES.mkdir(exist_ok=True)
INDEX = "http://127.0.0.1:8765/simple"
PKG = "supplydemo"
env = {}
for line in (FIX / "incident.env").read_text().splitlines():
    k, _, v = line.partition("=")
    env[k] = v
INCIDENT_START = env["INCIDENT_START"]
INCIDENT_MID = env["INCIDENT_MID"]
CLEAN_SHA = (FIX / f"{PKG}-1.0.0.sha256").read_text().strip()
BAD_SHA = (FIX / f"{PKG}-1.1.0.sha256").read_text().strip()

def run(cmd, cwd, env_extra=None):
    e = os.environ.copy()
    if env_extra:
        e.update(env_extra)
    p = subprocess.run(cmd, cwd=cwd, env=e, capture_output=True, text=True)
    return p.returncode, p.stdout, p.stderr

def check_marker(venv: Path) -> dict:
    # find site-packages
    sps = list(venv.glob("lib/python*/site-packages"))
    if not sps:
        sps = list(venv.glob("lib64/python*/site-packages"))
    sp = sps[0] if sps else None
    marker = None
    cook_pth = False
    version = None
    if sp:
        cook_pth = (sp / "cook.pth").is_file()
        # trigger import path: run python -c that starts interpreter (pth runs at startup)
        code, out, err = run([str(venv / "bin/python"), "-c",
            "import supplydemo, pathlib, sys; print(supplydemo.__version__); "
            "print('MARKER', (pathlib.Path(supplydemo.__file__).parent.parent / '_SUPPLYDEMO_MARKER').exists() or "
            "any(pathlib.Path(p).joinpath('_SUPPLYDEMO_MARKER').exists() for p in sys.path if p))"],
            cwd="/tmp")
        # marker written next to supplydemo_cook.py in site-packages
        mpath = sp / "_SUPPLYDEMO_MARKER"
        # cook module writes next to itself
        mpath2 = sp / "_SUPPLYDEMO_MARKER"
        # supplydemo_cook writes Path(__file__).parent / _SUPPLYDEMO_MARKER which is site-packages
        marker_present = mpath.is_file() or (sp / "_SUPPLYDEMO_MARKER").is_file()
        # force a fresh python start so .pth runs
        run([str(venv / "bin/python"), "-c", "pass"], cwd="/tmp")
        marker_present = (sp / "_SUPPLYDEMO_MARKER").is_file()
        code2, out2, err2 = run([str(venv / "bin/python"), "-c",
            "import importlib.metadata as m; print(m.version('supplydemo'))"], cwd="/tmp")
        version = out2.strip() if code2 == 0 else None
    return {
        "site_packages": str(sp) if sp else None,
        "cook_pth": cook_pth,
        "marker_file": marker_present if sp else False,
        "installed_version": version,
    }

strategies = []

def strategy(name, cmds, prep=None):
    strategies.append((name, cmds, prep))

# 1. unpinned — would resolve to newest (1.1.0)
strategy("unpinned_pip", [
    ["pip", "install", "--no-cache-dir", "--index-url", INDEX, "--trusted-host", "127.0.0.1", PKG],
])
# 2. == bad version
strategy("pin_eq_bad", [
    ["pip", "install", "--no-cache-dir", "--index-url", INDEX, "--trusted-host", "127.0.0.1", f"{PKG}==1.1.0"],
])
# 3. == clean
strategy("pin_eq_clean", [
    ["pip", "install", "--no-cache-dir", "--index-url", INDEX, "--trusted-host", "127.0.0.1", f"{PKG}==1.0.0"],
])
# 4. require-hashes with only clean hash (requirements file)
req_hash = RES / "requirements-hashed.txt"
req_hash.write_text(
    f"{PKG}==1.0.0 --hash=sha256:{CLEAN_SHA}\n"
)
strategy("require_hashes_clean_only", [
    ["pip", "install", "--no-cache-dir", "--index-url", INDEX, "--trusted-host", "127.0.0.1",
     "--require-hashes", "-r", str(req_hash)],
])
# 5. require-hashes but someone listed bad version with wrong/no matching — try installing bad with clean hash (should fail)
req_bad = RES / "requirements-bad-wrong-hash.txt"
req_bad.write_text(
    f"{PKG}==1.1.0 --hash=sha256:{CLEAN_SHA}\n"
)
strategy("require_hashes_bad_with_clean_hash", [
    ["pip", "install", "--no-cache-dir", "--index-url", INDEX, "--trusted-host", "127.0.0.1",
     "--require-hashes", "-r", str(req_bad)],
])
# 6. uv exclude-newer before incident
strategy("uv_exclude_newer_before_incident", [
    ["uv", "pip", "install", "--index-url", INDEX, "--exclude-newer", INCIDENT_START, PKG],
])
# 7. uv exclude-newer at mid-window (after bad upload) — newest allowed is bad
strategy("uv_exclude_newer_mid_window", [
    ["uv", "pip", "install", "--index-url", INDEX, "--exclude-newer", INCIDENT_MID, PKG],
])
# 8. pip uploaded-prior-to before incident
strategy("pip_uploaded_prior_to_before_incident", [
    ["pip", "install", "--no-cache-dir", "--index-url", INDEX, "--trusted-host", "127.0.0.1",
     "--uploaded-prior-to", INCIDENT_START, PKG],
])
# 9. pip uploaded-prior-to mid window
strategy("pip_uploaded_prior_to_mid_window", [
    ["pip", "install", "--no-cache-dir", "--index-url", INDEX, "--trusted-host", "127.0.0.1",
     "--uploaded-prior-to", INCIDENT_MID, PKG],
])

results = []
for name, cmds, prep in strategies:
    td = Path(tempfile.mkdtemp(prefix=f"sd-{name}-"))
    venv = td / "venv"
    print("==", name, flush=True)
    code, out, err = run([sys.executable, "-m", "venv", str(venv)], cwd=td)
    pip = str(venv / "bin/pip")
    # upgrade pip for --uploaded-prior-to
    run([pip, "install", "-q", "--upgrade", "pip==26.2.2"], cwd=td)
    # ensure uv available on PATH (system uv)
    logs = []
    final_code = 0
    for cmd in cmds:
        real = list(cmd)
        if real[0] == "pip":
            real[0] = pip
        if real[0] == "uv":
            # uv pip install into venv
            real = ["uv", "pip", "install", "--python", str(venv / "bin/python")] + real[3:]
        c, o, e = run(real, cwd=td)
        logs.append({"cmd": real, "code": c, "stdout": o[-2000:], "stderr": e[-2000:]})
        final_code = c
        if c != 0:
            break
    info = check_marker(venv) if final_code == 0 else {
        "site_packages": None, "cook_pth": False, "marker_file": False, "installed_version": None}
    outcome = "error"
    if final_code != 0:
        outcome = "refused"
    elif info.get("marker_file") or info.get("cook_pth") or info.get("installed_version") == "1.1.0":
        outcome = "installed_tampered"
    elif info.get("installed_version") == "1.0.0":
        outcome = "installed_clean"
    else:
        outcome = "installed_unknown"
    row = {"strategy": name, "exit_code": final_code, "outcome": outcome, **info, "logs": logs}
    results.append(row)
    print("  ->", outcome, "ver=", info.get("installed_version"), "marker=", info.get("marker_file"), "pth=", info.get("cook_pth"))
    shutil.rmtree(td, ignore_errors=True)

out_path = RES / "matrix.json"
out_path.write_text(json.dumps(results, indent=2) + "\n")
# markdown table
lines = ["# Install strategy matrix (local index)\n",
         f"Package: `{PKG}` clean=1.0.0 upload={env['CLEAN_UPLOAD']} / tampered=1.1.0 upload={env['BAD_UPLOAD']}\n",
         f"Incident window simulation: {INCIDENT_START} .. ~13:23 UTC; mid probe at {INCIDENT_MID}\n",
         "| strategy | outcome | version | cook.pth | marker |\n|---|---|---|---|---|\n"]
for r in results:
    lines.append(f"| `{r['strategy']}` | {r['outcome']} | {r.get('installed_version')} | {r.get('cook_pth')} | {r.get('marker_file')} |\n")
(RES / "matrix.md").write_text("".join(lines))
print("wrote", out_path)
