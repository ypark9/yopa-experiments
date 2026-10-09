# Run 2026-10-09T17:20:45-04:00 on Linux 6.12.94+ x86_64, 8 vCPU, rustc 1.99.0
# /tmp filesystem: overlay

## Verdict table

| Trace | What happens | Rule says | A stateless | B in-memory | C Dogwood |
| --- | --- | --- | --- | --- | --- |
| T1 | tests fail, push 5s later | DENY | DENY | DENY | DENY |
| T2 | tests pass, push 5s later | ALLOW | ALLOW | ALLOW | ALLOW |
| T3 | tests pass, push 17 min later | DENY | ALLOW (wrong) | DENY | DENY |
| T4 | pass, then fail, push | DENY | ALLOW (wrong) | DENY | DENY |
| T5 | no test run, agent claims tests passed | DENY | ALLOW (wrong) | DENY | DENY |
| T6 | tests pass, harness restarts, push | ALLOW | ALLOW | DENY (wrong) | ALLOW |
| T7 | tests pass, owner re-runs install() with same policies, push | ALLOW | ALLOW | ALLOW | DENY (wrong) |
| T8 | tests pass, owner widens push window 15m->30m via batch(Update), push | ALLOW | ALLOW | ALLOW | DENY (wrong) |
| T9 | same as T8, then tests re-run and push | ALLOW | ALLOW | ALLOW | ALLOW |

## Restart with the host clock stepped back

| Clock at reopen vs last stored event | Store opens? |
| --- | --- |
| 60 s behind | yes |
| 299 s behind | yes |
| 301 s behind | no: durable timestamp 1790001000000000002 is 301000000002 ns ahead of the current clock 1790000699000000000, excee |
| 600 s behind | no: durable timestamp 1790001000000000002 is 600000000002 ns ahead of the current clock 1790000400000000000, excee |

B in-memory gate: 0.0 ns per decision (1,000,000 decisions, 1000000 allowed)

## Push decision latency, disk (/tmp, fsync per event), 360 events/hour

| Session length | 15m window p50 / p90 (ms) | 24h window p50 / p90 (ms) |
| --- | --- | --- |
| 1 h | 0.671 / 0.968 | 1.470 / 2.442 |
| 2 h | 0.538 / 0.732 | 5.675 / 9.368 |
| 4 h | 0.506 / 0.543 | 25.210 / 28.952 |
| 8 h | 0.626 / 0.985 | 112.345 / 117.180 |
| 12 h | 0.604 / 0.646 | 239.417 / 266.749 |

## Push decision latency, RAM (/dev/shm), 360 events/hour

| Session length | 15m window p50 / p90 (ms) | 24h window p50 / p90 (ms) |
| --- | --- | --- |
| 1 h | 0.246 / 0.282 | 0.931 / 1.664 |
| 2 h | 0.247 / 0.253 | 5.220 / 7.009 |
| 4 h | 0.249 / 0.257 | 24.356 / 28.814 |
| 8 h | 0.370 / 0.395 | 170.412 / 181.295 |
| 12 h | 0.242 / 0.253 | 241.570 / 248.422 |

