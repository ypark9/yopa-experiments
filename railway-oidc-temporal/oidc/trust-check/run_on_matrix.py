"""Feed the seven matrix policies (as local JSON) to check_trust_policy.py, the Python half
of the article's read-only check. No AWS call."""
import json, subprocess, pathlib
here = pathlib.Path(__file__).parent
m = json.load(open(here.parent / "results" / "matrix.json"))
lines = []
for r in m["matrix"]:
    doc = {"Version": "2012-10-17", "Statement": [{"Effect": "Allow", "Condition": {r["operator"]: {
        "token.actions.githubusercontent.com:aud": "sts.amazonaws.com",
        "token.actions.githubusercontent.com:sub": r["sub_condition"]}}}]}
    p = subprocess.run(["python3", str(here / "check_trust_policy.py")], input=json.dumps(doc), capture_output=True, text=True)
    lines.append(f"{r['policy']}\texit={p.returncode}\t{p.stdout.strip()}")
(here / "results.txt").write_text("\n".join(lines) + "\n"); print("\n".join(lines))
