"""Does an older botocore even send AT_TIMESTAMP? Uses a Stubber: zero network."""
import botocore, boto3, json, sys
from botocore.stub import Stubber
from botocore.exceptions import ParamValidationError
c = boto3.client("dynamodbstreams", region_name="us-east-1", aws_access_key_id="x", aws_secret_access_key="x")
s = Stubber(c); s.activate()
arn = "arn:aws:dynamodb:us-east-1:000000000000:table/t/stream/2026-10-23T00:00:00.000"
shard = "shardId-00000000000000000000-00000000"
try:
    s.add_response("get_shard_iterator", {"ShardIterator": "stub"})
    c.get_shard_iterator(StreamArn=arn, ShardId=shard, ShardIteratorType="AT_TIMESTAMP", Timestamp=1792775189.76)
    print(json.dumps({"botocore": botocore.__version__, "result": "accepted (stubbed, nothing sent)"}))
except ParamValidationError as e:
    print(json.dumps({"botocore": botocore.__version__, "result": "ParamValidationError", "message": str(e)}))
