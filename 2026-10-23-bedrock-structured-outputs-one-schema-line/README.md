# Bedrock structured outputs: what one ordinary schema line does

Companion code for the yopa.page post `2026-10-23-bedrock-structured-outputs-one-schema-line`.

| File | What it does | Network | Ran by author |
|---|---|---|---|
| `schemas.py` | Nine Pydantic models, each one ordinary line away from a baseline | none | yes |
| `lint.py`, `run_lint.py` | Checks raw `model_json_schema()` and `anthropic.transform_schema()` output against the subset documented on the Bedrock structured-output page | none | yes |
| `mock_parse.py` | `AnthropicBedrock.messages.parse()` against an `httpx2.MockTransport`: captures the exact request body and feeds back replies that break a constraint | none (mock transport, dummy keys) | yes |
| `owner_run.py` | ~10 Claude Haiku 5.5 calls: cold vs warm, description vs structure change, the real 400 | **AWS, costs money** | **no** |

Run the free part: `python run_lint.py && python mock_parse.py`.

## Owner-run

```bash
python3 -m venv .venv && . .venv/bin/activate && pip install -r requirements.txt
aws sts get-caller-identity --query Arn --output text           # read-only: right account?
AWS_REGION=us-east-1 python owner_run.py --i-understand-this-uses-my-aws-account
```

Estimated cost: ~10 calls × (~150 input + ≤200 output tokens). At Anthropic's list price for Claude Haiku 5.5 ($0.10 / MTok input, $0.50 / MTok output, global routing) that is about $0.001. Confirm the Bedrock price for your Region on https://aws.amazon.com/bedrock/pricing/ (regional endpoints cost more). Nothing to tear down.
