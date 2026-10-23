"""What does AnthropicBedrock.messages.parse() actually put on the wire, and what happens
when the reply breaks a constraint the SDK moved into a description?
Zero network: httpx.MockTransport answers every request locally; dummy credentials."""
import json, os, anthropic, jsonschema
import httpx2 as httpx
for k in ("AWS_PROFILE", "AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_SESSION_TOKEN"): os.environ.pop(k, None)
os.environ["AWS_CONFIG_FILE"] = os.environ["AWS_SHARED_CREDENTIALS_FILE"] = "/dev/null"
from anthropic import AnthropicBedrock, transform_schema
from schemas import WithGe, WithMap, WithPattern
sent, replies = [], []
def handler(req: httpx.Request):
    sent.append({"url": str(req.url), "body": json.loads(req.content)})
    text = replies.pop(0)
    return httpx.Response(200, json={"id": "msg_local", "type": "message", "role": "assistant", "model": "mock",
        "content": [{"type": "text", "text": text}], "stop_reason": "end_turn", "stop_sequence": None,
        "usage": {"input_tokens": 1, "output_tokens": 1}})
c = AnthropicBedrock(aws_region="us-east-1", aws_access_key="DUMMY", aws_secret_key="DUMMY",
                     http_client=httpx.Client(transport=httpx.MockTransport(handler)), max_retries=0)
out = {"anthropic": anthropic.__version__}
def call(model, reply):
    replies.append(reply)
    try:
        r = c.messages.parse(model="global.anthropic.claude-haiku-5-5", max_tokens=200, output_format=model,
                             messages=[{"role": "user", "content": "classify"}])
        res = {"parsed": r.parsed_output.model_dump(mode="json")}
    except Exception as e:
        res = {"error": type(e).__name__, "detail": str(e).splitlines()[0:3]}
    res["wire_schema"] = sent[-1]["body"].get("output_config", {}).get("format", {}).get("schema")
    res["url_path"] = httpx.URL(sent[-1]["url"]).path
    return res
out["ge_violation"] = call(WithGe, '{"category":"billing","confidence":1.4}')
out["pattern_violation"] = call(WithPattern, '{"ticket":"ticket 42"}')
out["map_empty"] = call(WithMap, '{"category":"billing","tags":{}}')
# The grammar is built from the wire schema. Which tag maps can it ever accept?
wire = out["map_empty"]["wire_schema"]
orig = WithMap.model_json_schema()
sample = {"category": "billing", "tags": {"priority": "high"}}
out["map_check"] = {"sample": sample,
    "valid_under_original_pydantic_schema": jsonschema.Draft202012Validator(orig).is_valid(sample),
    "valid_under_wire_schema": jsonschema.Draft202012Validator(wire).is_valid(sample),
    "empty_map_valid_under_wire_schema": jsonschema.Draft202012Validator(wire).is_valid({"category": "billing", "tags": {}})}
print(json.dumps(out, indent=1))
json.dump(out, open("result-mock-parse.json", "w"), indent=1)
