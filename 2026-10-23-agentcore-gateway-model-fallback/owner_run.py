"""OWNER-RUN ONLY. Uses your AWS account and costs money (estimate: well under $0.05 at list price).

What it measures (all undocumented today):
  1. does the InvokeModel response body say which model actually served the request?
  2. once the primary keeps failing, how many primary attempts still reach Bedrock (breaker skip)?
  3. does a FIRST_BYTE_TIMEOUT'd primary attempt still show tokens on the primary model?
  4. after the primary recovers, how long until traffic returns to it (open + half-open time)?

Usage:
  export AWS_REGION=us-east-1
  export PRIMARY_MODEL=<an Anthropic Messages model/profile id you can invoke>
  export FALLBACK_MODEL=<a different Anthropic Messages model/profile id>
  python owner_run.py --i-understand-this-uses-my-aws-account
Everything it creates has a random suffix and is deleted in `finally`.
"""
import json, os, sys, time, uuid
if "--i-understand-this-uses-my-aws-account" not in sys.argv:
    sys.exit("refusing to run: pass --i-understand-this-uses-my-aws-account")
import boto3, botocore
from botocore.config import Config

def ver(v): return tuple(int(x) for x in v.split("."))
if ver(botocore.__version__) < (1, 43, 118):
    sys.exit(f"botocore {botocore.__version__} has no fallback/circuitBreaker fields; need >= 1.43.118")

REGION = os.environ["AWS_REGION"]
PRIMARY, FALLBACK = os.environ["PRIMARY_MODEL"], os.environ["FALLBACK_MODEL"]
assert PRIMARY != FALLBACK, "primary and fallback must differ (validation rule)"
SUFFIX = uuid.uuid4().hex[:8]
NAME = f"yopa-agw-fallback-{SUFFIX}"
iam, ctl, br, cw = (boto3.client(s, region_name=REGION) for s in ("iam", "bedrock-agentcore-control", "bedrock", "cloudwatch"))

# ---- read-only preflight -------------------------------------------------------------------
boto3.client("sts").get_caller_identity()          # fails fast if no credentials; prints nothing
ids = {m["modelId"] for m in br.list_foundation_models()["modelSummaries"]}
ids |= {p["inferenceProfileId"] for p in br.list_inference_profiles(maxResults=1000)["inferenceProfileSummaries"]}
for m in (PRIMARY, FALLBACK):
    if m not in ids: sys.exit(f"{m} is not listed in {REGION}; pick ids from list-foundation-models / list-inference-profiles")
print("preflight ok:", REGION, PRIMARY, "->", FALLBACK, "suffix", SUFFIX)

created = {}
out = {"region": REGION, "primary": PRIMARY, "fallback": FALLBACK, "botocore": botocore.__version__, "phases": {}}

def wait_ready(get, what, timeout=300):
    t0 = time.time()
    while time.time() - t0 < timeout:
        st = get()["status"]
        if st == "READY": return
        if "FAIL" in st: sys.exit(f"{what} status {st}")
        time.sleep(5)
    sys.exit(f"{what} not READY after {timeout}s")

def call(rt, text="Reply with the single word ok."):
    body = json.dumps({"anthropic_version": "bedrock-2023-05-31", "max_tokens": 16,
                       "messages": [{"role": "user", "content": text}]})
    t0 = time.time()
    try:
        r = rt.invoke_model(modelId=PRIMARY, body=body, contentType="application/json")
        b = json.loads(r["body"].read())
        return {"t": round(t0, 3), "ms": round((time.time() - t0) * 1000), "ok": True,
                "body_model": b.get("model"), "usage": b.get("usage"), "text": (b.get("content") or [{}])[0].get("text")}
    except botocore.exceptions.ClientError as e:
        return {"t": round(t0, 3), "ms": round((time.time() - t0) * 1000), "ok": False, "error": e.response["Error"]["Code"]}

def rule_actions(fbt_ms):
    return [{"routeToTarget": {"staticRoute": {"targetName": "bedrock", "model": PRIMARY, "fallback": {
        "circuitBreaker": {"mode": "ENABLED"},
        "triggerOn": {"statusCodes": ["429", "5XX"], "errors": ["CONNECTION_ERROR", "FIRST_BYTE_TIMEOUT"]},
        "firstByteTimeoutMilliseconds": fbt_ms,
        "targetFallback": [{"targetName": "bedrock", "model": FALLBACK}]}}}}]

try:
    trust = {"Version": "2012-10-17", "Statement": [{"Effect": "Allow", "Principal": {"Service": "bedrock-agentcore.amazonaws.com"}, "Action": "sts:AssumeRole"}]}
    role = iam.create_role(RoleName=NAME, AssumeRolePolicyDocument=json.dumps(trust))["Role"]; created["role"] = NAME
    iam.put_role_policy(RoleName=NAME, PolicyName="invoke", PolicyDocument=json.dumps({"Version": "2012-10-17", "Statement": [
        {"Effect": "Allow", "Action": ["bedrock:InvokeModel", "bedrock:InvokeModelWithResponseStream", "bedrock:List*"], "Resource": "*"}]}))
    time.sleep(15)  # IAM propagation
    gw = ctl.create_gateway(name=NAME, roleArn=role["Arn"], authorizerType="AWS_IAM")
    gid = gw["gatewayId"]; created["gateway"] = gid
    wait_ready(lambda: ctl.get_gateway(gatewayIdentifier=gid), "gateway")
    url = ctl.get_gateway(gatewayIdentifier=gid)["gatewayUrl"].rstrip("/")
    tgt = ctl.create_gateway_target(gatewayIdentifier=gid, name="bedrock",
        targetConfiguration={"inference": {"connector": {"source": {"connectorId": "bedrock-runtime"}}}},
        credentialProviderConfigurations=[{"credentialProviderType": "GATEWAY_IAM_ROLE"}])
    created["target"] = tgt["targetId"]
    wait_ready(lambda: ctl.get_gateway_target(gatewayIdentifier=gid, targetId=tgt["targetId"]), "target")
    rule = ctl.create_gateway_rule(gatewayIdentifier=gid, priority=100, description="yopa fallback probe",
        conditions=[{"matchModels": {"anyOf": [{"value": PRIMARY}]}}], actions=rule_actions(50))
    created["rule"] = rule["ruleId"]
    time.sleep(10)
    base = url if url.endswith("/inference") else url + "/inference"
    rt = boto3.client("bedrock-runtime", region_name=REGION, endpoint_url=base,
                      config=Config(retries={"mode": "standard", "max_attempts": 1}))

    # Phase 1: 40 requests, 1 every 1.5 s; the 50 ms first-byte timeout forces the primary to fail
    p1_start = time.time(); p1 = []
    for _ in range(40):
        p1.append(call(rt)); time.sleep(1.5)
    out["phases"]["1_forced_timeout"] = {"start": p1_start, "end": time.time(), "calls": p1}

    # Phase 2: "recover" the primary by raising its first-byte timeout, then watch traffic return
    ctl.update_gateway_rule(gatewayIdentifier=gid, ruleId=rule["ruleId"], priority=100,
        conditions=[{"matchModels": {"anyOf": [{"value": PRIMARY}]}}], actions=rule_actions(30000))
    p2_start = time.time(); p2 = []
    for _ in range(80):
        p2.append(call(rt)); time.sleep(1.5)
    out["phases"]["2_recovered"] = {"start": p2_start, "end": time.time(), "calls": p2}
finally:
    # ---- teardown (always) -------------------------------------------------------------------
    gid = created.get("gateway")
    try:
        if "rule" in created: ctl.delete_gateway_rule(gatewayIdentifier=gid, ruleId=created["rule"])
        if "target" in created:
            ctl.delete_gateway_target(gatewayIdentifier=gid, targetId=created["target"])
            for _ in range(60):
                if not ctl.list_gateway_targets(gatewayIdentifier=gid)["items"]: break
                time.sleep(5)
        if gid: ctl.delete_gateway(gatewayIdentifier=gid)
    finally:
        if "role" in created:
            iam.delete_role_policy(RoleName=NAME, PolicyName="invoke"); iam.delete_role(RoleName=NAME)
    print("teardown done:", sorted(created))

# ---- read the per-model Invocations / token metrics Bedrock publishes (1-minute buckets) ------
import datetime as dt
time.sleep(180)  # metric delay
t0 = out["phases"]["1_forced_timeout"]["start"] - 120
q = []
for i, m in enumerate((PRIMARY, FALLBACK)):
    for j, metric in enumerate(("Invocations", "InputTokenCount", "OutputTokenCount")):
        q.append({"Id": f"m{i}{j}", "Label": f"{m}|{metric}", "MetricStat": {"Metric": {"Namespace": "AWS/Bedrock",
                  "MetricName": metric, "Dimensions": [{"Name": "ModelId", "Value": m}]}, "Period": 60, "Stat": "Sum"}})
r = cw.get_metric_data(MetricDataQueries=q, StartTime=dt.datetime.fromtimestamp(t0, dt.timezone.utc),
                       EndTime=dt.datetime.now(dt.timezone.utc))
out["bedrock_metrics"] = {x["Label"]: list(zip([t.isoformat() for t in x["Timestamps"]], x["Values"])) for x in r["MetricDataResults"]}
os.makedirs("results", exist_ok=True)
with open(f"results/owner-run-{SUFFIX}.json", "w") as f: json.dump(out, f, indent=1, default=str)
print("wrote", f"results/owner-run-{SUFFIX}.json")
