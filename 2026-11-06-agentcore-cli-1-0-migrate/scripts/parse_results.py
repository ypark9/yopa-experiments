#!/usr/bin/env python3
"""Parse migrate stdout into a compact JSON table."""
from __future__ import annotations
import json, re, pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
OUT = ROOT / "results"
rows = []
for p in sorted(OUT.glob("*.txt")):
    if p.parent.name == "help":
        continue
    text = p.read_text(errors="ignore")
    m = re.search(r"Unrecognized key(?:s)?: ([^\n]+)", text)
    field_errs = re.findall(r"✖ ([^\n]+)\n\s*→ at ([^\n]+)", text)
    plan = "Migration plan:" in text
    already = "already in the v1 format" in text
    if "Failed to deserialize" in text:
        hint = "deserialize_fail"
    elif plan:
        hint = "plan_not_ready"
    elif already:
        hint = "already_v1"
    else:
        hint = "other"
    rows.append(
        {
            "fixture": p.stem,
            "unrecognized": m.group(1).strip() if m else None,
            "field_errors": [{"msg": a, "at": b} for a, b in field_errs],
            "reached_migrate_plan": plan,
            "already_v1": already,
            "exit_hint": hint,
        }
    )
(OUT / "parsed.json").write_text(json.dumps(rows, indent=2) + "\n")
print(f"wrote {OUT / 'parsed.json'} ({len(rows)} fixtures)")
