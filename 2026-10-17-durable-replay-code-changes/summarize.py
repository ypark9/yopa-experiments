#!/usr/bin/env python3
"""Builds results/matrix.md from results/run-*.jsonl and results/durablelint.json."""
import collections, glob, json, os, re

here = os.path.dirname(os.path.abspath(__file__))
res = os.path.join(here, "results")

# durablelint -json prints one JSON object per package: {pkg: {rule: [diag]}}
lint = collections.defaultdict(list)
raw = open(os.path.join(res, "durablelint.json")).read()
dec = json.JSONDecoder(); i = 0
while i < len(raw):
    if raw[i].isspace():
        i += 1; continue
    obj, i = dec.raw_decode(raw, i)
    for pkg, rules in obj.items():
        m = re.search(r"cases/([ab]\d\d)_", pkg)
        if not m:
            continue
        for rule, diags in rules.items():
            for d in diags:
                lint[m.group(1).upper()].append(rule)

rows = collections.OrderedDict()
per_run = collections.defaultdict(lambda: collections.Counter())
for path in sorted(glob.glob(os.path.join(res, "run-*.jsonl"))):
    for line in open(path):
        d = json.loads(line)
        r = rows.setdefault(d["case"], {"title": d["title"], "group": d["group"],
                                        "v": collections.Counter(), "golden": 0, "n": 0})
        r["v"][d["verdict"]] += 1
        r["golden"] += d["golden_would_fail"]
        r["n"] += 1
        per_run[(d["case"], d["run"])][d["verdict"]] += 1

def fmt(c):
    return ", ".join(f"{k} {v}" for k, v in sorted(c.items()))

print("| case | group | what | durablelint | outcome over all trials | golden signature would fail |")
print("|---|---|---|---|---|---|")
for cid, r in rows.items():
    l = lint.get(cid, [])
    lt = f"yes ({len(l)}: {', '.join(sorted(set(l)))})" if l else "no"
    print(f"| {cid} | {r['group']} | {r['title']} | {lt} | {fmt(r['v'])} (n={r['n']}) | {r['golden']}/{r['n']} |")
print()
print("Per run (verdict counts out of the trials in that run):")
print()
for (cid, run), c in sorted(per_run.items()):
    if len(rows[cid]["v"]) > 1:
        print(f"- {cid} run {run}: {fmt(c)}")
print()
print("Verdicts: ok = succeeded and output consistent; silent = succeeded but output inconsistent "
      "(A: keys/totals disagree with what invocation 1 checkpointed; B: differs from a fresh run of the new code); "
      "nde = failed with NonDeterministicExecutionError on replay; error:<type> = failed with another error on replay; "
      "first-run-error:<type> = failed before any replay.")
