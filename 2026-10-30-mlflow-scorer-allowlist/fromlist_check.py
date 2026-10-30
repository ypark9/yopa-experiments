"""Shows the Python behavior behind MLflow 3.17.0's new `metric_name.isidentifier()` check.

MLflow 3.16.1's deepeval wrapper resolves an unknown metric with
    __import__("deepeval.metrics", fromlist=[f"{metric_name}Metric"])
This script asks one question with a throwaway package: if `metric_name` contains a dot,
does that `__import__` call import (and therefore execute) a submodule the caller placed
under the package? It does not use deepeval or MLflow. Harmless marker only.
"""
import json, os, secrets, shutil, sys, tempfile

base = tempfile.mkdtemp(prefix="fromlist-"); marker_dir = tempfile.mkdtemp(prefix="marker-")
token = secrets.token_hex(8)
os.makedirs(os.path.join(base, "simeval", "metrics", "upload"))
open(os.path.join(base, "simeval", "__init__.py"), "w").close()
open(os.path.join(base, "simeval", "metrics", "__init__.py"), "w").write("class FaithfulnessMetric:\n    pass\n")
open(os.path.join(base, "simeval", "metrics", "upload", "probeMetric.py"), "w").write(
    f"open({os.path.join(marker_dir, 'marker.txt')!r}, 'w').write({token!r})\n")
sys.path.insert(0, base)
out = []
for metric_name in ["Faithfulness", "upload.probe"]:
    marker = os.path.join(marker_dir, "marker.txt")
    if os.path.exists(marker): os.remove(marker)
    err = None
    try:
        mod = __import__("simeval.metrics", fromlist=[f"{metric_name}Metric"])
    except Exception as e:
        err = type(e).__name__
    ran = os.path.exists(marker) and open(marker).read() == token
    out.append({"metric_name": metric_name, "passes_isidentifier": metric_name.isidentifier(),
                "caller_code_ran": ran, "error": err})
shutil.rmtree(base); shutil.rmtree(marker_dir)
print(json.dumps({"python": sys.version.split()[0], "rows": out}, indent=2))
