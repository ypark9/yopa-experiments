# Does a model refuse a dangerous tool call on its own?

Code and raw data for [Your Agent's Refusal Only Covers the Rules You Wrote Down. I Measured the Rest.](https://www.yopa.page/blog/2026-09-26-where-should-agent-refusals-live.html)

## What it does

A fake support agent for a store called Acme, with five tools: `search_docs`, `send_email`, `issue_refund`, `delete_customer_record`, `export_customers`.

**The tools are fake.** Each one returns a fixed string, and nothing is executed (see `run_case` in `run.py`). The harness only records which tool the model asked for, and with which arguments.

The only real network calls are model calls:

- Amazon Bedrock, the `Converse` API (`bedrock-runtime`)
- Fireworks AI, `https://us.api.fireworks.ai/inference/v1/chat/completions` (models whose ID starts with `fw:`)

It sends 25 requests: 5 dangerous ones, each worded 4 ways, plus 5 normal ones as a control. Each request runs under 2 system prompts, `no_rules` and `prompt_rules`. Every tool call is scored by `gate()` in `run.py`, which checks the same rules a Cedar policy on a gateway would check.

## Result (719 trials, 0 errors, about $4.80)

| Model | `no_rules`: bad calls | `prompt_rules`: bad calls |
| --- | --- | --- |
| Amazon Nova Pro | 52 / 60 | 0 / 60 |
| Claude Haiku 4.5 | 35 / 60 | 0 / 60 |
| GLM 5.3 (US) | 8 / 60 | 0 / 60 |
| Kimi K3 (US) | 7 / 60 | 0 / 44 (stopped at 119 of 150 trials) |
| Claude Sonnet 5 | 4 / 60 | 0 / 60 |

Normal requests: the gate blocked 0 of 135 by mistake, and the models completed 135 of 135.

`final_analysis.txt` is the full output of `analyze.py` on this data.

## Files

| File | What |
| --- | --- |
| `run.py` | the harness. Flags: `--dry-run`, `--ping`, `--only`, `--repeats`. It resumes from the output file. `ONLY_COND=no_rules` or `ONLY_COND=prompt_rules` runs one prompt only |
| `analyze.py` | builds the tables and the cost estimate: `python3 analyze.py full_*.jsonl` |
| `full_1.jsonl` to `full_5.jsonl`, `full_4b.jsonl` | raw trials. 1 Sonnet 5, 2 Haiku 4.5, 3 Nova Pro, 4 and 4b Kimi K3 (US), 5 GLM 5.3 (US) |
| `final_analysis.txt` | `analyze.py` output |

## Running it

```bash
python3 run.py --dry-run --models x          # prints the plan, no calls

export AWS_PROFILE=<your-profile>            # an account with Bedrock model access
export FIREWORKS_API_KEY=...                 # only for fw: models
python3 run.py --ping --models us.anthropic.claude-haiku-4-5-20251001-v1:0
python3 run.py --repeats 3 --out mine.jsonl \
  --models us.anthropic.claude-haiku-4-5-20251001-v1:0,fw:accounts/fireworks/routers/glm-5p3-us
python3 analyze.py mine.jsonl
```

If you are behind a TLS-inspecting proxy, set `EXTRA_CA_BUNDLE` to its CA bundle. Some proxy CAs do not mark Basic Constraints as critical, and Python 3.13 rejects them in strict mode. `run.py` then loads the bundle and drops only that one strict flag. Certificate verification stays on.

A full run of 150 trials per model costs about $0.30 to $2 per model at list prices on 2026-09-26. Kimi K3 (US) is the most expensive, and much slower.

## What this does not prove

- **Single requests only.** No long conversations, no pressure over many turns, no attacker who adapts.
- **One made-up scenario with five simple rules.**
- **Three runs per request.** That is enough to see 0 against 87%, but not enough to tell 7% from 13%.
- **The gate blocking bad calls is by design.** The gate and the scorer use the same rules. What the data measures is the models' behavior and the gate's false blocks.
- **Kimi K3 (US) is incomplete.** Its `prompt_rules` rows have no injection trials and no normal requests.
- **Costs are estimates.** Token counts are real. Prices are public list prices, and Sonnet 5 is assumed to cost the same as other Sonnet models.
