"""DynamoDB Streams AT_TIMESTAMP probe against DynamoDB Local ONLY.
Refuses to run unless the endpoint is loopback. Dummy credentials. No AWS calls."""
import os, sys, time, json, datetime as dt
from urllib.parse import urlparse
ENDPOINT = os.environ.get("DDB_ENDPOINT", "http://127.0.0.1:8765")
assert urlparse(ENDPOINT).hostname in ("127.0.0.1", "localhost"), "loopback only"
os.environ.update(AWS_ACCESS_KEY_ID="local", AWS_SECRET_ACCESS_KEY="local",
                  AWS_CONFIG_FILE="/dev/null", AWS_SHARED_CREDENTIALS_FILE="/dev/null",
                  AWS_EC2_METADATA_DISABLED="true")
import boto3, botocore
from botocore.exceptions import ClientError, ParamValidationError
kw = dict(endpoint_url=ENDPOINT, region_name="us-east-1")
ddb = boto3.client("dynamodb", **kw); st = boto3.client("dynamodbstreams", **kw)
out = {"botocore": botocore.__version__}
T = "probe"
try: ddb.delete_table(TableName=T)
except ClientError: pass
ddb.create_table(TableName=T, AttributeDefinitions=[{"AttributeName":"pk","AttributeType":"S"}],
    KeySchema=[{"AttributeName":"pk","KeyType":"HASH"}], BillingMode="PAY_PER_REQUEST",
    StreamSpecification={"StreamEnabled":True,"StreamViewType":"KEYS_ONLY"})
arn = ddb.describe_table(TableName=T)["Table"]["LatestStreamArn"]
writes = []
def put(i):
    ddb.put_item(TableName=T, Item={"pk":{"S":f"item-{i:03d}"}})
    writes.append((i, time.time()))
# burst A: 6 writes within ~1 second, then pause, burst B
for i in range(6): put(i); time.sleep(0.15)
time.sleep(2.2)
for i in range(6, 12): put(i); time.sleep(0.15)
shard = st.describe_stream(StreamArn=arn)["StreamDescription"]["Shards"][0]["ShardId"]
def read(**it):
    try:
        itr = st.get_shard_iterator(StreamArn=arn, ShardId=shard, **it)["ShardIterator"]
    except (ClientError, ParamValidationError) as e:
        return {"error": type(e).__name__ + ": " + str(e)[:200]}
    recs = []
    for _ in range(5):
        r = st.get_records(ShardIterator=itr); recs += r["Records"]
        itr = r.get("NextShardIterator")
        if not itr or not r["Records"]: break
    return {"keys":[x["dynamodb"]["Keys"]["pk"]["S"] for x in recs],
            "approx":[x["dynamodb"]["ApproximateCreationDateTime"].timestamp() for x in recs]}
out["writes_client_time"] = writes
th = read(ShardIteratorType="TRIM_HORIZON"); out["TRIM_HORIZON"] = th
out["approx_has_fraction"] = any(a % 1 for a in th.get("approx", []))
out["LATEST"] = read(ShardIteratorType="LATEST")
# resume points derived from record 3 (middle of burst A)
if "approx" in th:
    a3 = th["approx"][3]
    out["resume_at_last_seen"] = {"ts": a3, **read(ShardIteratorType="AT_TIMESTAMP", Timestamp=a3)}
    out["resume_at_last_seen_plus_1ms"] = {"ts": a3+0.001, **read(ShardIteratorType="AT_TIMESTAMP", Timestamp=a3+0.001)}
    w3 = writes[3][1]
    out["resume_at_client_write_time_of_item3"] = {"ts": w3, **read(ShardIteratorType="AT_TIMESTAMP", Timestamp=w3)}
out["AT_TIMESTAMP_old_1970"] = read(ShardIteratorType="AT_TIMESTAMP", Timestamp=1.0)
out["AT_TIMESTAMP_future_+1h"] = read(ShardIteratorType="AT_TIMESTAMP", Timestamp=time.time()+3600)
out["AT_TIMESTAMP_no_Timestamp"] = read(ShardIteratorType="AT_TIMESTAMP")
print(json.dumps(out, indent=1, default=str))
