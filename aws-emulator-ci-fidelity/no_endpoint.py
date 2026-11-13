import boto3
c = boto3.client("sts")
print("ENDPOINT_USED", c.meta.endpoint_url)
try:
    print("RESULT ok account-len", len(c.get_caller_identity()["Account"]))
except Exception as e:
    print("RESULT error", type(e).__name__, str(e)[:200])
