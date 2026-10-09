# Push only after green tests: where does the test history live?

Code and raw output for the yopa.page post "My push gate forgot the test run" (draft, 2026-10-09).

## What it does

One rule for a coding agent: `git:push` is allowed only if a test run passed in the last 15 minutes and no run has failed since. This is the example rule from the AWS post [Introducing the Dogwood Local Engine](https://aws.amazon.com/blogs/opensource/introducing-the-dogwood-local-engine-temporal-governance-for-agent-actions/).

Three gates decide the same nine event traces:

- **A, stateless.** Decides from the push request alone, like a per-call Cedar policy. The only thing it can check is a `tests_passed` field the agent puts in the request.
- **B, in-memory.** The harness keeps the last test result and its time in a variable. No disk.
- **C, Dogwood Local Engine** `dogwood-local-engine` at commit `d2cba92` (the 1.0.0 tree), durable redb store, temporal policy from the AWS post.

**Nothing runs.** No tool, no git, no network call, no model. The clock is injected (`DurableConfig::with_clock`), so "17 minutes later" takes no real time.

It also measures how long the engine takes per push decision over a simulated 12-hour session at 360 events per hour (the rate in the AWS post), for a 15-minute and a 24-hour window, on disk (fsync per event) and on `/dev/shm` (RAM), with two event mixes:

- dense: every other event is a passing test run (180 per hour)
- sparse: 12 test runs per hour, the rest are file reads

## Run

```bash
cargo build --release
./target/release/push-gate-harness 12   # 12 = session hours
```

Needs a Rust toolchain new enough for the engine's dependencies (built here with rustc 1.99.0; 1.85 was too old). Cost: none.

## Output

`results.md` is the full output of the run used in the post (2026-10-09, Linux x86_64, 8 vCPU, `/tmp` on overlayfs). An earlier run of the dense mix gave the same verdicts and latencies within about 10%; its file was dropped because the raw error text tripped the identifier scan.
