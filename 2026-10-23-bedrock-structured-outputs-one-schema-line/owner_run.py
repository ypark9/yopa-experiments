"""OWNER-RUN ONLY. About 10 small Claude Haiku 5.5 calls on Amazon Bedrock in YOUR account.
Measures cold vs warm latency of structured outputs, what a description-only change does,
what a structure change does, and the exact 400 for an unsupported schema keyword.
Estimated cost: well under $0.01 at list price (see README). Not run by the author.
Usage: AWS_REGION=us-east-1 python owner_run.py --i-understand-this-uses-my-aws-account"""
import sys, json, time, uuid
if "--i-understand-this-uses-my-aws-account" not in sys.argv:
    sys.exit("refusing to run: pass --i-understand-this-uses-my-aws-account")
import boto3
from botocore.config import Config
from botocore.exceptions import ClientError
from anthropic import transform_schema
from schemas import Baseline, WithGe, WithMap
MODEL = "global.anthropic.claude-haiku-5-5"
rt = boto3.client("bedrock-runtime", config=Config(read_timeout=600, retries={"max_attempts": 1}))
PROMPT = "Ticket: 'I was charged twice for my October invoice, please fix.' Classify it."
run_id = uuid.uuid4().hex[:6]          # makes the first schema new to the grammar cache

def call(label, schema):
    body = {"anthropic_version": "bedrock-2023-05-31", "max_tokens": 200,
            "messages": [{"role": "user", "content": PROMPT}],
            "output_config": {"format": {"type": "json_schema", "schema": schema}}}
    t0 = time.perf_counter()
    try:
        r = json.loads(rt.invoke_model(modelId=MODEL, body=json.dumps(body))["body"].read())
        res = {"ok": True, "stop_reason": r.get("stop_reason"), "usage": r.get("usage"),
               "text": r["content"][0].get("text") if r.get("content") else None}
    except ClientError as e:
        res = {"ok": False, "status": e.response["ResponseMetadata"]["HTTPStatusCode"],
               "code": e.response["Error"]["Code"], "message": e.response["Error"]["Message"]}
    res["seconds"] = round(time.perf_counter() - t0, 2); res["label"] = label
    print(json.dumps(res)); return res

base = transform_schema(Baseline)
base["properties"][f"note_{run_id}"] = {"type": "string"}; base["required"].append(f"note_{run_id}")
out = [call("1 cold: new structure", base)]
out += [call(f"2 warm: same schema #{i}", base) for i in range(1, 4)]
desc = json.loads(json.dumps(base)); desc["properties"]["reason"]["description"] = "one short sentence"
out.append(call("3 description-only change", desc))
struct = json.loads(json.dumps(base)); struct["properties"]["urgent"] = {"type": "boolean"}; struct["required"].append("urgent")
out.append(call("4 structure change", struct))
out.append(call("5 raw pydantic schema with ge/le (no SDK transform)", WithGe.model_json_schema()))
out.append(call("6 SDK-transformed dict[str,str] field", transform_schema(WithMap)))
json.dump(out, open("result-owner-run.json", "w"), indent=1)
