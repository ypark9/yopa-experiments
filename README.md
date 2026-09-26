# yopa-experiments

Code and raw data behind the measured posts on [yopa.page](https://www.yopa.page).
One folder per post, named after the post.

| Folder | Post | What it measures |
| --- | --- | --- |
| [`2026-09-26-where-should-agent-refusals-live`](2026-09-26-where-should-agent-refusals-live/) | [Your Agent's Refusal Only Covers the Rules You Wrote Down](https://www.yopa.page/blog/2026-09-26-where-should-agent-refusals-live.html) | 719 tool-calling trials across 5 models, with and without rules in the prompt, scored by a deterministic gate |
| [`2026-09-26-who-can-start-your-agent-sandbox`](2026-09-26-who-can-start-your-agent-sandbox/) | [Who Is Allowed to Start Your Agent's Sandbox?](https://www.yopa.page/blog/2026-09-26-who-can-start-your-agent-sandbox.html) | a webhook launcher's checks (38 local tests), an IAM secret split, and 50 copies of one webhook at once against DynamoDB |

## Rules for this repo

- **Every folder has a README** that says what the experiment actually calls, what it creates, what it costs, and what it does not prove.
- **Raw data is included.** The tables in the posts are computed from the files here, so you can check them.
- **Nothing identifies an account.** No AWS account IDs, profile names, internal names, or owner tags. Where an ARN has to appear, it uses the AWS documentation placeholder `123456789012`. `scripts/check-identifiers.sh` enforces this on every push and pull request.
- **Anything that creates AWS resources says so at the top**, and has a matching teardown step.

## Before you run anything

Some experiments call paid APIs (Amazon Bedrock, Fireworks AI) or create AWS resources. Read the folder's README first. Use a disposable account.

## License

MIT. See [LICENSE](LICENSE).
