# A team of bots on AgentCore: the starter stack and where the money goes

Code and output behind the post
[A Team of Bots on AgentCore: Start With 20 Resources, Budget for Tokens](https://www.yopa.page/blog/2026-11-22-agentcore-bot-team-start-to-production.html).

**Nothing here calls AWS or a model, and nothing creates AWS resources.** Everything runs on your machine.

| Folder | What it does | Output |
| --- | --- | --- |
| `runtime/` | The smallest HTTP server that follows the AgentCore Runtime contract (`GET /ping`, `POST /invocations` streaming server-sent events). Node built-ins only. `check.sh` starts it on a local port and sends four requests. | `results/runtime-check.txt` |
| `cdk/` | The starter stack: one DynamoDB table, one AgentCore Memory, one AgentCore Runtime with its role, one Lambda, one REST API with a Cognito sign-in. `npm run synth` builds the CloudFormation template locally and counts its resources. | `results/synth-resource-count.txt` |
| `cost/` | Turns the usage measured on my prototype (token counts, vCPU-hours, GB-hours, memory events) into dollars at the public prices of 2026-11-22. Arithmetic only. | `results/cost.txt` |

## Run it

```bash
./runtime/check.sh                       # needs Node 22+ and curl
(cd cdk && npm install && npm run synth) # downloads aws-cdk-lib 2.275.0, no AWS credentials needed
python3 cost/cost.py
```

## What it costs

- Local: CPU time on your machine.
- CI: this repo's `identifier-check` job.
- Cloud: none. `cdk synth` writes a template to `cdk/cdk.out/`; it does not deploy.

## What it does not prove

- **The stack was not deployed.** `synth` passing means the template builds, not that the runtime starts, that
  `usingPublicNetwork()` reaches Bedrock, or that a 15-minute stream works through API Gateway with a Cognito
  authorizer.
- **The Lambda handler is a placeholder** that returns 501. A real one calls `InvokeAgentRuntime` and passes the
  event stream on.
- **The usage numbers come from my prototype** (6 days, 32 agent runs, one user). They cannot be rerun from this
  repo. Only the arithmetic can be checked.
- **Prices change.** The script records the prices used and the date.
