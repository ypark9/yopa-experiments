"""Run realistic CI-style checks against a local AWS Emulator (loopback only, no AWS account)."""
import boto3, botocore, json, time, os, sys
from botocore.config import Config
out = []
def rec(case, expected_on_aws, observed, verdict, note=""):
    out.append({"case": case, "expected_on_aws": expected_on_aws, "observed_in_emulator": observed, "verdict": verdict, "note": note})
    print(json.dumps(out[-1]), flush=True)
def err(e):
    if isinstance(e, botocore.exceptions.ClientError):
        r = e.response
        return f"{r['Error'].get('Code')} (HTTP {r['ResponseMetadata'].get('HTTPStatusCode')}): {r['Error'].get('Message','')[:160]}"
    return f"{type(e).__name__}: {str(e)[:200]}"
cfg = Config(retries={"max_attempts": 1})
s = boto3.session.Session()
sts = s.client("sts", config=cfg)
ident = sts.get_caller_identity()
acct = ident["Account"]
print("caller account (raw, will be sanitized):", acct, file=sys.stderr)

# 1 DynamoDB conditional put
ddb = s.client("dynamodb", config=cfg)
ddb.create_table(TableName="orders", AttributeDefinitions=[{"AttributeName": "pk", "AttributeType": "S"}],
                 KeySchema=[{"AttributeName": "pk", "KeyType": "HASH"}], BillingMode="PAY_PER_REQUEST")
ddb.get_waiter("table_exists").wait(TableName="orders")
ddb.put_item(TableName="orders", Item={"pk": {"S": "o-1"}}, ConditionExpression="attribute_not_exists(pk)")
try:
    ddb.put_item(TableName="orders", Item={"pk": {"S": "o-1"}}, ConditionExpression="attribute_not_exists(pk)")
    rec("DynamoDB: second insert of the same order id with attribute_not_exists", "ConditionalCheckFailedException", "accepted", "DIFFERENT")
except Exception as e:
    o = err(e); rec("DynamoDB: second insert of the same order id with attribute_not_exists", "ConditionalCheckFailedException", o, "SAME" if "ConditionalCheckFailed" in o else "DIFFERENT")

# 2 S3 conditional write
s3 = s.client("s3", config=cfg)
s3.create_bucket(Bucket="ci-artifacts")
s3.put_object(Bucket="ci-artifacts", Key="lock.json", Body=b"{}", IfNoneMatch="*")
try:
    s3.put_object(Bucket="ci-artifacts", Key="lock.json", Body=b"{}", IfNoneMatch="*")
    rec("S3: second create-only write (If-None-Match: *) to the same key", "PreconditionFailed (HTTP 412)", "accepted", "DIFFERENT")
except Exception as e:
    o = err(e); rec("S3: second create-only write (If-None-Match: *) to the same key", "PreconditionFailed (HTTP 412)", o, "SAME" if "412" in o else "DIFFERENT")

# 3 IAM user with explicit deny
iam = s.client("iam", config=cfg)
iam.create_user(UserName="reader")
iam.put_user_policy(UserName="reader", PolicyName="deny-get", PolicyDocument=json.dumps({"Version": "2012-10-17", "Statement": [
    {"Effect": "Allow", "Action": "s3:*", "Resource": "*"},
    {"Effect": "Deny", "Action": "s3:GetObject", "Resource": "arn:aws:s3:::ci-artifacts/*"}]}))
k = iam.create_access_key(UserName="reader")["AccessKey"]
s3u = boto3.client("s3", aws_access_key_id=k["AccessKeyId"], aws_secret_access_key=k["SecretAccessKey"], config=cfg)
try:
    s3u.get_object(Bucket="ci-artifacts", Key="lock.json")
    rec("IAM: user whose own policy explicitly denies s3:GetObject reads the object", "AccessDenied (explicit deny wins)", "read succeeded", "DIFFERENT")
except Exception as e:
    o = err(e); rec("IAM: user whose own policy explicitly denies s3:GetObject reads the object", "AccessDenied (explicit deny wins)", o, "SAME" if "AccessDenied" in o else "DIFFERENT")

# 4 Bucket policy deny, request signed with the emulator's own key
s3.put_bucket_policy(Bucket="ci-artifacts", Policy=json.dumps({"Version": "2012-10-17", "Statement": [
    {"Effect": "Deny", "Principal": "*", "Action": "s3:GetObject", "Resource": "arn:aws:s3:::ci-artifacts/*"}]}))
try:
    s3.get_object(Bucket="ci-artifacts", Key="lock.json")
    rec("S3: bucket policy denies s3:GetObject to every principal; read with the default (emulator) key", "AccessDenied for IAM principals", "read succeeded", "DIFFERENT",
        "Emulator docs: it never denies a request signed with its own key and doesn't check bucket policies.")
except Exception as e:
    o = err(e); rec("S3: bucket policy denies s3:GetObject to every principal; read with the default (emulator) key", "AccessDenied for IAM principals", o, "SAME" if "AccessDenied" in o else "DIFFERENT")

# 5 SQS visibility timeout
sqs = s.client("sqs", config=cfg)
q = sqs.create_queue(QueueName="jobs")["QueueUrl"]
sqs.send_message(QueueUrl=q, MessageBody="job-1")
m1 = sqs.receive_message(QueueUrl=q, VisibilityTimeout=2, WaitTimeSeconds=1).get("Messages", [])
m_hidden = sqs.receive_message(QueueUrl=q, WaitTimeSeconds=0).get("Messages", [])
time.sleep(3)
m2 = sqs.receive_message(QueueUrl=q, WaitTimeSeconds=1).get("Messages", [])
obs = f"first receive={len(m1)}, immediate second receive={len(m_hidden)}, after 3 s={len(m2)}"
rec("SQS: message hidden for 2 s after receive, then visible again", "first receive=1, immediate second receive=0, after 3 s=1", obs,
    "SAME" if (len(m1), len(m_hidden), len(m2)) == (1, 0, 1) else "DIFFERENT")

# 6 Bedrock Runtime Converse
br = s.client("bedrock-runtime", config=cfg)
try:
    r = br.converse(modelId="us.anthropic.claude-sonnet-5-5", messages=[{"role": "user", "content": [{"text": "hi"}]}])
    rec("Bedrock Runtime: Converse call", "a model response (billed)", "returned a response: " + str(r.get("output"))[:120], "N/A")
except Exception as e:
    rec("Bedrock Runtime: Converse call", "a model response (billed)", err(e), "N/A", "Shows whether model calls can run offline in CI.")

# 7 AgentCore runtime invoke
try:
    ac = s.client("bedrock-agentcore", config=cfg)
    ac.invoke_agent_runtime(agentRuntimeArn="arn:aws:bedrock-agentcore:us-east-1:%s:runtime/demo-abc123" % acct, payload=b"{}")
    rec("AgentCore: InvokeAgentRuntime on a runtime that was never created", "ResourceNotFoundException", "accepted", "DIFFERENT")
except Exception as e:
    rec("AgentCore: InvokeAgentRuntime on a runtime that was never created", "ResourceNotFoundException", err(e), "N/A")

json.dump(out, open(sys.argv[1], "w"), indent=1)
