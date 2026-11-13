"""Second batch: behaviors where a passing local test can still mislead."""
import boto3, botocore, json, time, sys, base64
from botocore.config import Config
out = []
def rec(case, expected_on_aws, observed, verdict, note=""):
    out.append({"case": case, "expected_on_aws": expected_on_aws, "observed_in_emulator": observed, "verdict": verdict, "note": note}); print(json.dumps(out[-1]), flush=True)
def err(e):
    if isinstance(e, botocore.exceptions.ClientError):
        r = e.response; return f"{r['Error'].get('Code')} (HTTP {r['ResponseMetadata'].get('HTTPStatusCode')}): {r['Error'].get('Message','')[:160]}"
    return f"{type(e).__name__}: {str(e)[:200]}"
cfg = Config(retries={"max_attempts": 1})
s = boto3.session.Session()
acct = s.client("sts").get_caller_identity()["Account"]
iam = s.client("iam", config=cfg); s3 = s.client("s3", config=cfg)
s3.create_bucket(Bucket="b2-bucket"); s3.put_object(Bucket="b2-bucket", Key="k", Body=b"x")
# A: user with no policy at all (implicit deny)
iam.create_user(UserName="nopolicy"); k = iam.create_access_key(UserName="nopolicy")["AccessKey"]
c = boto3.client("s3", aws_access_key_id=k["AccessKeyId"], aws_secret_access_key=k["SecretAccessKey"], config=cfg)
try:
    c.get_object(Bucket="b2-bucket", Key="k"); rec("IAM: brand-new user with no policies reads an object", "AccessDenied (no allow = implicit deny)", "read succeeded", "DIFFERENT")
except Exception as e:
    o = err(e); rec("IAM: brand-new user with no policies reads an object", "AccessDenied (no allow = implicit deny)", o, "SAME" if "AccessDenied" in o else "DIFFERENT")
# B: KMS key policy that grants nobody but root; user with kms:* in IAM tries Decrypt
kms = s.client("kms", config=cfg)
kid = kms.create_key(Policy=json.dumps({"Version": "2012-10-17", "Statement": [{"Sid": "root-only", "Effect": "Allow", "Principal": {"AWS": f"arn:aws:iam::{acct}:root"}, "Action": "kms:*", "Resource": "*"},
     {"Sid": "deny-app", "Effect": "Deny", "Principal": {"AWS": f"arn:aws:iam::{acct}:user/app"}, "Action": "kms:Decrypt", "Resource": "*"}]}))["KeyMetadata"]["KeyId"]
blob = kms.encrypt(KeyId=kid, Plaintext=b"secret")["CiphertextBlob"]
iam.create_user(UserName="app"); iam.put_user_policy(UserName="app", PolicyName="kms", PolicyDocument=json.dumps({"Version": "2012-10-17", "Statement": [{"Effect": "Allow", "Action": "kms:*", "Resource": "*"}]}))
k2 = iam.create_access_key(UserName="app")["AccessKey"]
kc = boto3.client("kms", aws_access_key_id=k2["AccessKeyId"], aws_secret_access_key=k2["SecretAccessKey"], config=cfg)
try:
    kc.decrypt(CiphertextBlob=blob); rec("KMS: key policy explicitly denies Decrypt to user 'app'; app decrypts", "AccessDeniedException (key policy deny wins)", "decrypt succeeded", "DIFFERENT", "Emulator docs say KMS key policies are not checked.")
except Exception as e:
    o = err(e); rec("KMS: key policy explicitly denies Decrypt to user 'app'; app decrypts", "AccessDeniedException (key policy deny wins)", o, "SAME" if "AccessDenied" in o else "DIFFERENT")
# C: GSI read right after write
ddb = s.client("dynamodb", config=cfg)
ddb.create_table(TableName="users", AttributeDefinitions=[{"AttributeName": "pk", "AttributeType": "S"}, {"AttributeName": "email", "AttributeType": "S"}],
    KeySchema=[{"AttributeName": "pk", "KeyType": "HASH"}], BillingMode="PAY_PER_REQUEST",
    GlobalSecondaryIndexes=[{"IndexName": "by-email", "KeySchema": [{"AttributeName": "email", "KeyType": "HASH"}], "Projection": {"ProjectionType": "ALL"}}])
ddb.get_waiter("table_exists").wait(TableName="users")
hits = 0
for i in range(200):
    ddb.put_item(TableName="users", Item={"pk": {"S": f"u{i}"}, "email": {"S": f"u{i}@example.com"}})
    r = ddb.query(TableName="users", IndexName="by-email", KeyConditionExpression="email = :e", ExpressionAttributeValues={":e": {"S": f"u{i}@example.com"}})
    hits += r["Count"]
rec("DynamoDB: query a GSI immediately after each of 200 writes", "eventually consistent; an immediate read can miss the item (docs-based, not run)", f"found {hits} of 200 immediately", "N/A",
    "A test that expects the item on the very next GSI read passes locally every time; on AWS it can flake.")
# D: strongly consistent read on GSI (AWS rejects)
try:
    ddb.query(TableName="users", IndexName="by-email", ConsistentRead=True, KeyConditionExpression="email = :e", ExpressionAttributeValues={":e": {"S": "u1@example.com"}})
    rec("DynamoDB: ConsistentRead=True on a GSI query", "ValidationException (GSIs don't support strongly consistent reads)", "accepted", "DIFFERENT")
except Exception as e:
    o = err(e); rec("DynamoDB: ConsistentRead=True on a GSI query", "ValidationException (GSIs don't support strongly consistent reads)", o, "SAME" if "Validation" in o else "DIFFERENT")
# E: Bedrock converse stub, full
br = s.client("bedrock-runtime", config=cfg)
r = br.converse(modelId="us.anthropic.claude-sonnet-5-5", messages=[{"role": "user", "content": [{"text": "Return the JSON {\"ok\": true}"}]}])
rec("Bedrock Runtime: Converse asking for JSON", "model text (billed per token)", json.dumps({"text": r["output"]["message"]["content"][0].get("text"), "stopReason": r.get("stopReason"), "usage": r.get("usage")})[:400], "N/A",
    "A test that only checks 'got a non-empty reply' passes against a placeholder.")
try:
    br.converse(modelId="not-a-real-model", messages=[{"role": "user", "content": [{"text": "hi"}]}])
    rec("Bedrock Runtime: Converse with a model id that does not exist", "ValidationException / ResourceNotFound", "accepted", "DIFFERENT")
except Exception as e:
    o = err(e); rec("Bedrock Runtime: Converse with a model id that does not exist", "ValidationException / ResourceNotFound", o, "SAME" if ("Validation" in o or "NotFound" in o) else "DIFFERENT")
json.dump(out, open(sys.argv[1], "w"), indent=1)
