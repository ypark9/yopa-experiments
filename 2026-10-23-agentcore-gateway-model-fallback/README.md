# AgentCore Gateway model fallback: a local mock of the circuit breaker

Companion to the yopa.page post on AgentCore Gateway InvokeModel support and model fallback (launched 2026-10-22).

## What runs for free (no AWS calls)
- `gateway_mock.py` is a stdlib-only simulation of ordered fallback with a per-destination circuit breaker.
  - It encodes the documented rules (D1–D8 in the file header) from the [fallback guide](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/gateway-rules-fallback.html).
  - Every number AWS does not publish is in `ASSUMED`: open threshold, open duration, half-open fraction, close rule, all-open behavior, whether abandoned attempts bill tokens, and whether the body names the served model.
  - It writes `results/result-mock.json` with 13 scenario runs and a 12-point sweep over open duration and probe fraction.
  - Model costs are relative units, not dollars. The gateway cost uses $0.005 per 1,000 invocations from the [AgentCore pricing page](https://aws.amazon.com/bedrock/agentcore/pricing/).
- `validate_shapes.py` checks the owner-run request shapes against the local botocore 1.43.118 service model.
  - It shows `circuitBreaker` accepts only `mode` and that the first-byte timeout floor is 50 ms.
  - Client-side validation does not catch a third fallback or an unknown error name.
- `./run.sh` runs both.

## Owner-run (not yet run; costs money)
`owner_run.py --i-understand-this-uses-my-aws-account` does the following:
- creates one IAM role, one gateway (AWS_IAM inbound), one `bedrock-runtime` connector target and one rule
- forces the primary to fail with a 50 ms first-byte timeout (40 calls), then raises the timeout to 30 s (80 calls)
- deletes everything in `finally`, then reads the free per-model Bedrock metrics

Estimate: about 120 requests with `max_tokens` 16 means about 240 gateway attempts, about $0.0012 in gateway fees plus well under a cent of model tokens. A few CloudWatch `GetMetricData` metrics add a fraction of a cent. Billing is unconfirmed until the bill shows it.

Before running it:
1. Use CLI v2 or boto3 with botocore >= 1.43.118. The fallback fields first appear in that version; 1.43.115–117 have `CreateGatewayRule` without them.
2. Pick two Anthropic Messages models you can invoke: `aws bedrock list-inference-profiles --query "inferenceProfileSummaries[].inferenceProfileId"`. Both must take the same payload schema, because the gateway does not convert one payload schema into another.

Teardown check afterward:
- `aws bedrock-agentcore-control list-gateways --query "items[?starts_with(name,'yopa-agw-fallback')]"` should return `[]`
- `aws iam list-roles --query "Roles[?starts_with(RoleName,'yopa-agw-fallback')].RoleName"` should return `[]`
