# Push only after green tests: where does the test history live?

Code and raw output for the yopa.page post "Push Only After Green Tests: Where Should My Agent's Gate Keep the History?" (draft, 2026-10-09).

## What it does

One rule for a coding agent: `git:push` is allowed only if a test run **for the same repo and the same commit** passed in the last 15 minutes and no run of that repo and commit has failed since. The unscoped version of this rule is the example in the AWS post [Introducing the Dogwood Local Engine](https://aws.amazon.com/blogs/opensource/introducing-the-dogwood-local-engine-temporal-governance-for-agent-actions/).

Four gates decide the same twelve event traces:

- **A, stateless.** Decides from the push request alone, like a per-call Cedar policy. The only thing it can check is a `tests_passed` field the agent puts in the request. It still trusts the agent.
- **B, in-memory.** The harness keeps the latest test result and its time per (repo, tested commit) in a map. No disk.
- **C, Dogwood Local Engine** `dogwood-local-engine` at commit `d2cba92` (the 1.0.0 tree), durable redb store, temporal policy correlated on `input.repo` and `input.sha` (the pattern `input.user: context.input.user` from the engine README).
- **C0, Dogwood with the policy exactly as in the AWS post** (no correlation), run on the same traces to show what it does when one history covers several repos or commits.

Traces T10 to T12 cover the shared-history cases: tests pass on repo A, then a push on repo B; tests pass on commit X, then a push of commit Y; tests pass on A, fail on B, then a push on A.

**Nothing runs.** No tool, no git, no network call, no model. The clock is injected (`DurableConfig::with_clock`), so "17 minutes later" takes no real time.

It also times the engine's whole push `submit()` call (persist the event, then evaluate; not evaluation alone) over a simulated 12-hour session at 360 events per hour (the rate in the AWS post), for a 15-minute and a 24-hour window, on disk (fsync per event) and on `/dev/shm` (RAM). Each checkpoint reports the median and p90 of the last 10 pushes in that hour. A push is every 30th event (12 per hour). Two event mixes:

- dense: per hour 180 tests requests + 168 passing tests responses + 12 pushes (each push replaces one response)
- sparse: per hour 12 tests requests + 12 passing tests responses + 324 file reads + 12 pushes

The correlated policy (C) is timed on both disks and both mixes. The uncorrelated one (C0) is timed on disk, both mixes, in the same run, for comparison. All latency events use one repo and one commit, so every tests response matches either policy.

## Run

```bash
cargo build --release
./target/release/push-gate-harness 12   # 12 = session hours
```

Needs a Rust toolchain new enough for the engine's dependencies (built here with rustc 1.99.0; 1.85 was too old). Cost: none.

## Output

`results.md` is the full output of the run used in the post (2026-10-09, Linux x86_64, 8 vCPU, `/tmp` on overlayfs). It replaces the first run, which used the uncorrelated policy only and nine traces; that output is in this branch's git history.
