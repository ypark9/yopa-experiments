# Lambda Web Functions vs Event Functions: desk math

Companion code for the yopa.page post `2026-10-23-lambda-web-functions-cost-math`.

| File | What it does | Network | Ran by author |
|---|---|---|---|
| `cost_model.py` | Reprices AWS's four Web Functions examples as Event Functions (Arm and x86), with and without CPU scaling by memory, and with more than one environment | none | yes |
| `sse_cpu.mjs`, `run.sh` | Local stand-in for an LLM streaming proxy (300 chunks over ~3 s). Measures process CPU per request at concurrency 1/8/64 with `process.cpuUsage()` | 127.0.0.1 only | yes (Node 20.19.2, x86 box, includes the load client) |
| `load.mjs` | Fixed-concurrency load generator, refuses n > 5000 | the URL you give it | only against 127.0.0.1 |
| `bill_from_metrics.py` | Turns the free `AWS/Lambda/Web` metrics from an owner run into an estimated bill | none | yes (with made-up inputs) |

Prices: US East (N. Virginia), first tier, free tier excluded, 2026-10-23.
- Web: from the worked examples on https://aws.amazon.com/lambda/pricing/
- Event: from the page's public price map, https://b0.p.awsstatic.com/pricing/2.0/meteredUnitMaps/lambda/USD/current/lambda.json

Owner-run steps, cost and teardown are in the post.
