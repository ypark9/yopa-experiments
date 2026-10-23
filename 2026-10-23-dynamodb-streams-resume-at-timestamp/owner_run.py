"""OWNER-RUN ONLY. Creates a real on-demand DynamoDB table with a stream in YOUR account,
writes 12 tiny items, reads the stream with AT_TIMESTAMP, then deletes the table.
Estimated cost: well under $0.01 (see README). Not run by the author.
Usage: AWS_REGION=us-east-1 python owner_run.py --i-understand-this-uses-my-aws-account"""
import sys, time, json, uuid, os
if "--i-understand-this-uses-my-aws-account" not in sys.argv:
    sys.exit("refusing to run: pass --i-understand-this-uses-my-aws-account")
import boto3, botocore
from botocore.config import Config
from botocore.exceptions import ClientError
from packaging.version import Version
assert Version(botocore.__version__) >= Version("1.43.114"), "botocore 1.43.114+ needed for AT_TIMESTAMP"
cfg = Config(retries={"max_attempts": 1, "mode": "standard"})   # fail fast, no retry storms
ddb = boto3.client("dynamodb", config=cfg); st = boto3.client("dynamodbstreams", config=cfg)
T = f"yopa-at-timestamp-{uuid.uuid4().hex[:8]}"                 # never touches an existing table
out = {"botocore": botocore.__version__, "region": ddb.meta.region_name, "table": T}
try:
    ddb.create_table(TableName=T, AttributeDefinitions=[{"AttributeName": "pk", "AttributeType": "S"}],
        KeySchema=[{"AttributeName": "pk", "KeyType": "HASH"}], BillingMode="PAY_PER_REQUEST",
        StreamSpecification={"StreamEnabled": True, "StreamViewType": "KEYS_ONLY"},
        Tags=[{"Key": "purpose", "Value": "yopa-at-timestamp-test"}])
    ddb.get_waiter("table_exists").wait(TableName=T)
    arn = ddb.describe_table(TableName=T)["Table"]["LatestStreamArn"]
    writes = []
    def put(i):
        ddb.put_item(TableName=T, Item={"pk": {"S": f"item-{i:03d}"}}); writes.append((i, time.time()))
    for i in range(6): put(i); time.sleep(0.12)        # burst A: ~6 writes inside 1-2 seconds
    time.sleep(2.5)
    for i in range(6, 12): put(i); time.sleep(0.12)    # burst B
    time.sleep(3)                                      # let records land in the stream
    shard = st.describe_stream(StreamArn=arn)["StreamDescription"]["Shards"][0]["ShardId"]
    def read(**it):
        try: itr = st.get_shard_iterator(StreamArn=arn, ShardId=shard, **it)["ShardIterator"]
        except ClientError as e: return {"error": e.response["Error"]["Code"] + ": " + e.response["Error"]["Message"][:200]}
        recs = []
        for _ in range(10):
            r = st.get_records(ShardIterator=itr); recs += r["Records"]; itr = r.get("NextShardIterator")
            if not itr or (recs and not r["Records"]): break
            time.sleep(0.3)
        return {"keys": [x["dynamodb"]["Keys"]["pk"]["S"] for x in recs],
                "approx": [x["dynamodb"]["ApproximateCreationDateTime"].timestamp() for x in recs]}
    out["writes_client_time"] = writes
    th = read(ShardIteratorType="TRIM_HORIZON"); out["TRIM_HORIZON"] = th
    out["approx_has_fraction"] = any(a % 1 for a in th.get("approx", []))
    if th.get("approx"):
        a3 = th["approx"][3]
        out["resume_at_last_seen"] = {"ts": a3, **read(ShardIteratorType="AT_TIMESTAMP", Timestamp=a3)}
        out["resume_at_last_seen_plus_1ms"] = {"ts": a3 + 0.001, **read(ShardIteratorType="AT_TIMESTAMP", Timestamp=a3 + 0.001)}
        out["resume_at_client_write_time_of_item3"] = {"ts": writes[3][1], **read(ShardIteratorType="AT_TIMESTAMP", Timestamp=writes[3][1])}
    out["AT_TIMESTAMP_1970"] = read(ShardIteratorType="AT_TIMESTAMP", Timestamp=1.0)
    out["AT_TIMESTAMP_future_plus_1h"] = read(ShardIteratorType="AT_TIMESTAMP", Timestamp=time.time() + 3600)
finally:
    try:
        ddb.delete_table(TableName=T); ddb.get_waiter("table_not_exists").wait(TableName=T)
        out["teardown"] = "table deleted"
    except ClientError as e:
        out["teardown"] = "DELETE FAILED, delete it by hand: " + str(e)
    print(json.dumps(out, indent=1, default=str))
    json.dump(out, open("result-owner-run.json", "w"), indent=1, default=str)
