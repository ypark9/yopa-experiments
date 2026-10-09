# Run 2026-10-09T17:21:37-04:00 on Linux 6.12.94+ x86_64, 8 vCPU, rustc 1.99.0, dogwood-local-engine d2cba92
# /tmp filesystem: overlay; /dev/shm: tmpfs

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

B in-memory gate: 1.2 ns per decision (1,000,000 decisions, 1000000 allowed)

## Push decision latency, disk (/tmp, fsync per event), 360 events/hour, dense: 180 green test runs/hour

| Session length | 15m: push p50 / p90 (ms) | 15m: mean per event that hour (ms) | 24h: push p50 / p90 (ms) | 24h: mean per event that hour (ms) |
| --- | --- | --- | --- | --- |
| 1 h | 0.563 / 0.961 | 0.455 | 1.232 / 2.241 | 0.443 |
| 2 h | 0.528 / 0.681 | 0.495 | 5.460 / 8.236 | 0.624 |
| 4 h | 0.567 / 0.840 | 0.421 | 28.407 / 29.572 | 1.378 |
| 8 h | 0.730 / 1.127 | 0.515 | 108.868 / 114.335 | 4.001 |
| 12 h | 0.543 / 0.611 | 0.380 | 246.287 / 253.302 | 8.482 |

## Push decision latency, RAM (/dev/shm), 360 events/hour, dense: 180 green test runs/hour

| Session length | 15m: push p50 / p90 (ms) | 15m: mean per event that hour (ms) | 24h: push p50 / p90 (ms) | 24h: mean per event that hour (ms) |
| --- | --- | --- | --- | --- |
| 1 h | 0.245 / 0.262 | 0.076 | 0.930 / 1.715 | 0.095 |
| 2 h | 0.242 / 0.247 | 0.075 | 5.265 / 6.649 | 0.226 |
| 4 h | 0.245 / 0.249 | 0.078 | 24.532 / 27.228 | 0.822 |
| 8 h | 0.244 / 0.247 | 0.077 | 104.352 / 105.565 | 3.417 |
| 12 h | 0.240 / 0.249 | 0.078 | 243.688 / 261.359 | 8.121 |

## Push decision latency, disk (/tmp, fsync per event), 360 events/hour, sparse: 12 test runs/hour, rest file reads

| Session length | 15m: push p50 / p90 (ms) | 15m: mean per event that hour (ms) | 24h: push p50 / p90 (ms) | 24h: mean per event that hour (ms) |
| --- | --- | --- | --- | --- |
| 1 h | 0.435 / 0.873 | 0.518 | 0.587 / 0.807 | 0.455 |
| 2 h | 0.440 / 0.655 | 0.471 | 0.942 / 1.016 | 0.517 |
| 4 h | 0.428 / 0.592 | 0.471 | 2.246 / 2.418 | 0.566 |
| 8 h | 0.573 / 0.593 | 0.460 | 7.979 / 8.555 | 0.734 |
| 12 h | 0.450 / 0.523 | 0.477 | 26.364 / 27.224 | 1.499 |

## Push decision latency, RAM (/dev/shm), 360 events/hour, sparse: 12 test runs/hour, rest file reads

| Session length | 15m: push p50 / p90 (ms) | 15m: mean per event that hour (ms) | 24h: push p50 / p90 (ms) | 24h: mean per event that hour (ms) |
| --- | --- | --- | --- | --- |
| 1 h | 0.166 / 0.176 | 0.120 | 0.176 / 0.235 | 0.095 |
| 2 h | 0.171 / 0.195 | 0.130 | 0.494 / 0.582 | 0.107 |
| 4 h | 0.168 / 0.173 | 0.127 | 1.787 / 2.084 | 0.143 |
| 8 h | 0.117 / 0.125 | 0.091 | 7.687 / 7.974 | 0.341 |
| 12 h | 0.110 / 0.125 | 0.088 | 18.518 / 22.902 | 0.786 |

