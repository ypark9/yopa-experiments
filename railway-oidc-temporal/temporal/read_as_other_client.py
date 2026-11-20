"""Act as a second client that holds only network access to the frontend (what Railway calls
a trusted client) and no codec key. Uses the plain temporal CLI. For each workflow, dump
history and describe output, base64-decode every payload `data` field, and search for the
fake marker. Records which event types / fields leaked it."""
import base64, json, subprocess, sys
T = sys.argv[1] if len(sys.argv) > 1 else "./temporal"
cases = json.load(open("results/cases_run.json"))

def run(*a):
    return subprocess.run([T, *a, "--address", "localhost:7233", "-o", "json"],
                          capture_output=True, text=True, check=True).stdout

def walk(o, path, hits, marker):
    if isinstance(o, dict):
        for k, v in o.items():
            walk(v, f"{path}.{k}", hits, marker)
    elif isinstance(o, list):
        for i, v in enumerate(o): walk(v, f"{path}[]", hits, marker)
    elif isinstance(o, str):
        cands = [o]
        try: cands.append(base64.b64decode(o, validate=True).decode("utf-8", "ignore"))
        except Exception: pass
        if any(marker in c for c in cands): hits.add(path)

listing = json.loads("[" + ",".join(l for l in run("workflow", "list").splitlines() if l.strip()) + "]") \
    if run("workflow", "list").strip().startswith("{") else json.loads(run("workflow", "list"))
report = {"workflows_listed_by_other_client": len(listing), "cases": []}
for c in cases:
    wid = f"build-{c['case']}"
    hist = json.loads(run("workflow", "show", "-w", wid))
    desc = json.loads(run("workflow", "describe", "-w", wid))
    hh, dh = set(), set()
    walk(hist, "history", hh, c["marker"]); walk(desc, "describe", dh, c["marker"])
    events = [e.get("eventType") for e in hist.get("events", [])]
    report["cases"].append({**{k: c[k] for k in ("case", "description", "codec", "encoded_failures")},
                            "secret_readable_without_key": bool(hh or dh),
                            "leaking_fields": sorted(hh | dh), "event_types": events})
json.dump(report, open("results/other_client_view.json", "w"), indent=2)
for c in report["cases"]:
    print(c["case"], "LEAK" if c["secret_readable_without_key"] else "clean", c["leaking_fields"])
print("workflows visible to the other client:", report["workflows_listed_by_other_client"])
