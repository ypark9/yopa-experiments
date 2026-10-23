#!/usr/bin/env python3
"""Build clean and 'tampered' wheels for supplydemo. Tampered plants a marker via .pth only."""
from __future__ import annotations
import base64, hashlib, io, os, struct, time, zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIX = ROOT / "fixtures"
FIX.mkdir(parents=True, exist_ok=True)

NAME = "supplydemo"
# Simulated incident window (UTC), mirroring LiteLLM Oct 21 11:39–13:23
CLEAN_UPLOAD = "2026-10-21T10:44:22.902887Z"   # like 1.106.2 before the bad release
BAD_UPLOAD = "2026-10-21T11:40:00.000000Z"     # inside the bad window
INCIDENT_START = "2026-10-21T11:39:51Z"
INCIDENT_MID = "2026-10-21T12:00:00Z"

def wheel_bytes(version: str, files: dict[str, bytes]) -> bytes:
    # Minimal pure-python wheel
    tag = "py3-none-any"
    wheel_name = f"{NAME}-{version}-{tag}.whl"
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as z:
        for path, data in files.items():
            z.writestr(path, data)
        dist = f"{NAME}-{version}.dist-info"
        metadata = f"Metadata-Version: 2.1\nName: {NAME}\nVersion: {version}\nSummary: local fixture for install-strategy test\n"
        z.writestr(f"{dist}/METADATA", metadata)
        z.writestr(f"{dist}/WHEEL", "Wheel-Version: 1.0\nGenerator: yopa-fixture\nRoot-Is-Purelib: true\nTag: py3-none-any\n")
        # RECORD filled loosely
        record_lines = []
        for info in z.infolist():
            data = z.read(info.filename)
            h = hashlib.sha256(data).digest()
            record_lines.append(f"{info.filename},sha256={base64.urlsafe_b64encode(h).decode().rstrip('=')},{len(data)}")
        record_lines.append(f"{dist}/RECORD,,")
        z.writestr(f"{dist}/RECORD", "\n".join(record_lines) + "\n")
    return buf.getvalue()

def write_wheel(version: str, files: dict[str, bytes], upload_time: str) -> Path:
    data = wheel_bytes(version, files)
    path = FIX / f"{NAME}-{version}-py3-none-any.whl"
    path.write_bytes(data)
    meta = FIX / f"{NAME}-{version}.upload-time"
    meta.write_text(upload_time + "\n")
    sha = hashlib.sha256(data).hexdigest()
    (FIX / f"{NAME}-{version}.sha256").write_text(sha + "\n")
    print(version, path.name, "sha256="+sha, "upload="+upload_time)
    return path

# Clean 1.0.0: package code only
clean_files = {
    f"{NAME}/__init__.py": b'__version__ = "1.0.0"\n',
}
write_wheel("1.0.0", clean_files, CLEAN_UPLOAD)

# Tampered 1.1.0: same package + cook.pth style marker (harmless)
# cook.pth content that writes a marker when imported - we use a tiny module
marker_mod = b'''# fixture only - NOT malware
from pathlib import Path
Path(__file__).resolve().parent.joinpath("_SUPPLYDEMO_MARKER").write_text("installed-tampered\\n")
'''
bad_files = {
    f"{NAME}/__init__.py": b'__version__ = "1.1.0"\n',
    "cook.pth": b"import supplydemo_cook\n",
    "supplydemo_cook.py": marker_mod,
}
write_wheel("1.1.0", bad_files, BAD_UPLOAD)

# Sidecar for the index server
(FIX / "incident.env").write_text(
    f"INCIDENT_START={INCIDENT_START}\nINCIDENT_MID={INCIDENT_MID}\n"
    f"CLEAN_UPLOAD={CLEAN_UPLOAD}\nBAD_UPLOAD={BAD_UPLOAD}\n"
    f"PACKAGE={NAME}\n"
)
print("fixtures ready in", FIX)
