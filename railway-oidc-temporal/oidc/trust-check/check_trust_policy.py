import json, sys
doc = json.load(sys.stdin); bad = 0
for st in doc.get("Statement", []):
    for op, kv in st.get("Condition", {}).items():
        for key, vals in kv.items():
            if not key.endswith(":sub"):
                continue
            for v in vals if isinstance(vals, list) else [vals]:
                why = []
                if "*" in v or "?" in v: why.append("wildcard")
                if v.startswith("repo:") and "/" not in v.split(":", 2)[1]: why.append("owner not closed by / (other owners can match)")
                if v.endswith(":*") or v.endswith("/*"): why.append("any branch/PR/tag or any repo")
                print(("WIDE " if why else "ok   ") + op + " " + v + ("  <- " + ", ".join(why) if why else ""))
                bad |= bool(why)
sys.exit(bad)
