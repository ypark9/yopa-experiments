# Would the evaluator catch the $40 refund?

Code and raw results for
[the post](https://www.yopa.page/blog/2026-09-28-would-the-evaluator-catch-the-wrong-refund.html).

A Strands agent answers one refund question with a policy-search tool. Its spans are captured in
memory (nothing is sent to CloudWatch), converted with `convert_strands_to_adot` from the
AgentCore SDK, and scored by the AgentCore `Evaluate` API.

| Condition | Tool returns | Runs |
|---|---|---|
| `stale` | last quarter's policy, $40 | 10 |
| `fresh` | current policy, $140 | 10 |
| `fee` | current policy, and the system prompt adds a $20 fee (positive control) | 10 |

Evaluators: `Builtin.Correctness`, `Builtin.Faithfulness`, `Builtin.Helpfulness`,
`Builtin.GoalSuccessRate` without ground truth, plus `Builtin.Correctness` with an expected
response and `Builtin.GoalSuccessRate` with an assertion.

## Run

```bash
python3 -m venv .venv && . .venv/bin/activate && pip install -r requirements.txt
AWS_PROFILE=<your-profile> ./go.sh 10 myrun            # stale + fresh
AWS_PROFILE=<your-profile> ./go.sh 10 myfee fee        # control
python analyze.py results/*.jsonl
python check_sysprompt.py   # does the system prompt reach the Evaluate input?
```

AWS calls: Bedrock `Converse` (the agent, Claude Haiku 4.5 in us-east-1) and
`bedrock-agentcore:Evaluate`. No resources are created. The 30 runs above used 180 `Evaluate`
calls and about 204k judge tokens.

## Results (2026-09-28)

```
answers: stale $40 x10, fresh $140 x10, fee $120 x10
evaluator                    stale ($40)          fresh ($140)          fee ($120)
correctness_no_gt     mean 1.00 pass 10/10  mean 1.00 pass 10/10  mean 0.50 pass 0/10
faithfulness          mean 1.00 pass 10/10  mean 1.00 pass 10/10  mean 0.35 pass 2/10
helpfulness           mean 0.86 pass 10/10  mean 0.92 pass 10/10  mean 0.17 pass 0/10
goal_no_gt            mean 1.00 pass 10/10  mean 1.00 pass 10/10  mean 0.00 pass 0/10
correctness_gt        mean 0.00 pass  0/10  mean 1.00 pass 10/10  mean 0.00 pass 0/10
goal_assert           mean 0.00 pass  0/10  mean 1.00 pass 10/10  mean 0.00 pass 0/10
```

"pass" means a score of 0.7 or higher. `check_sysprompt.py` found the system prompt in the raw
Strands spans but not in the converted ADOT documents.

Note: `run.py` gained the `fee` condition after `full10.jsonl` was recorded. The `stale` and
`fresh` code paths did not change.
