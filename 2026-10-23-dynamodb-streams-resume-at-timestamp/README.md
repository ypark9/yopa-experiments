# DynamoDB Streams AT_TIMESTAMP: where do you resume from?

Companion code for the yopa.page post `2026-10-23-dynamodb-streams-resume-at-timestamp`.

Nothing in this folder calls AWS except `owner_run.py`, which refuses to start without an explicit flag.

| File | What it does | Network | Ran by author |
|---|---|---|---|
| `simulate.py` | Model of the documented AT_TIMESTAMP rules (second-floored `ApproximateCreationDateTime`, at-or-after match, trim-horizon fallback, future = error). 71,799 writes at 20/s, 200 crashes, 60 s downtime, six resume strategies | none | yes |
| `oldsdk.py` | Does botocore accept `ShardIteratorType=AT_TIMESTAMP` + `Timestamp`? botocore Stubber, nothing is sent | none | yes, 1.43.113 and 1.43.118 |
| `probe.py` | Same questions against DynamoDB Local 3.3.2 on 127.0.0.1 (refuses any other host, dummy credentials) | loopback only | yes |
| `owner_run.py` | Same probe against a real, throwaway on-demand table, then deletes it | **AWS, costs money** | **no** |

## Results (author's box, 2026-10-23)

- `results/result-oldsdk-1.43.113.json`: `ParamValidationError: Unknown parameter in input: "Timestamp"`. 1.43.118 accepts it. From the wheels' `service-2.json`, 1.43.114 is the first botocore that has both.
- `results/result-botocore-1.43.118.json`: DynamoDB Local 3.3.2 returns `InternalFailure` for every `AT_TIMESTAMP` call (5 variants), and stamps every record's `ApproximateCreationDateTime` to the start of the minute. You cannot test this feature locally.
- `results/result-simulation.json`: see the table in the post. The model encodes the docs; it is not a measurement of the service.

## Owner-run

```bash
python3 -m venv .venv && . .venv/bin/activate && pip install -r requirements.txt
aws sts get-caller-identity --query Arn --output text   # read-only: right account and role?
AWS_REGION=us-east-1 python owner_run.py --i-understand-this-uses-my-aws-account
aws dynamodb list-tables --query "TableNames[?starts_with(@, 'yopa-at-timestamp-')]"   # expect []
```

Estimated cost: one on-demand table for a few minutes, 12 writes, under 100 stream reads. List prices in us-east-1 (2026-10-23): $0.625 per million write request units, $0.02 per 100,000 stream read request units, first 2.5M stream reads per month free. Rough total: well under $0.01.
