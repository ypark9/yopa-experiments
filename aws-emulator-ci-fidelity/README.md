# AWS Emulator in CI: what a green local test proves (2026-11-13)

Local checks against [AWS Emulator](https://github.com/aws/aws-emulator) **v1.0.343** (release 2026.11.13, repo commit `a9f10fef3b8215b13ffc390ace27bdd58f2aac00`), run on one Linux box.

## Safety and cost

- No AWS account, no AWS calls. The emulator `.deb` came from the public download host.
- Everything ran inside `unshare -rn` (a network namespace with loopback only), so even a misconfigured SDK could not reach real AWS.
- The box's real AWS keys were removed with `env -i` before anything started.
- Emulator telemetry was turned off with `--telemetry off`.
- The emulator reports an all-zero account ID; outputs were rewritten to the placeholder `123456789012`, and emulator access key IDs in the log are redacted.

## Run

```sh
env -i PATH=/usr/sbin:/usr/bin:/bin EMU_HOME=$PWD/home EMU_BIN=/path/to/aws-emulator \
  RAW=$PWD/raw EXP=$PWD PY=/path/to/python-with-boto3 unshare -rn ./inner.sh
```

boto3 1.44.2, Python 3.13.

## Files

| File | What it holds |
|---|---|
| `checks.py`, `raw/checks.json` | DynamoDB conditional put, S3 create-only put, IAM explicit deny, bucket-policy deny, SQS visibility timeout, Bedrock Converse, AgentCore InvokeAgentRuntime |
| `checks2.py`, `raw/checks2.json` | IAM implicit deny, KMS key-policy deny, GSI read after 200 writes, GSI ConsistentRead, Bedrock Converse JSON prompt, invalid model ID |
| `no_endpoint.py`, `raw/no-endpoint*.txt` | Which endpoint boto3 uses when `AWS_ENDPOINT_URL` is unset, with and without the emulator's config file |
| `raw/scores-by-service-v1.0.343.json` | Pass/fail counts per service, summarized from the release's published `scores.json.gz` |
| `raw/emulator.log` | Emulator log for the run (telemetry disabled line, created resources) |

"Expected on AWS" values come from AWS documentation. Nothing was compared against a live AWS account.
