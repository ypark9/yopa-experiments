# Run 2026-10-09T17:26:09-04:00 on Linux 6.12.94+ x86_64, 8 vCPU, rustc 1.99.0, dogwood-local-engine d2cba92
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
| 301 s behind | no: durable timestamp is ahead of the current clock beyond max_future_skew |
| 600 s behind | no: durable timestamp is ahead of the current clock beyond max_future_skew |

B in-memory gate: 1.0 ns per decision (1,000,000 decisions, 1000000 allowed)

## Push decision latency, disk (/tmp, fsync per event), 360 events/hour, dense: 180 green test runs/hour

| Session length | 15m: push p50 / p90 (ms) | 15m: mean per event that hour (ms) | 24h: push p50 / p90 (ms) | 24h: mean per event that hour (ms) |
| --- | --- | --- | --- | --- |
| 1 h | 0.601 / 0.807 | 0.388 | 1.442 / 2.188 | 0.417 |
| 2 h | 0.554 / 0.680 | 0.405 | 6.884 / 7.328 | 0.585 |
| 4 h | 0.669 / 0.962 | 0.387 | 25.644 / 29.633 | 1.179 |
| 8 h | 0.640 / 0.724 | 0.478 | 114.972 / 119.585 | 4.229 |
| 12 h | 0.709 / 0.787 | 0.445 | 242.510 / 262.072 | 8.500 |

## Push decision latency, RAM (/dev/shm), 360 events/hour, dense: 180 green test runs/hour

| Session length | 15m: push p50 / p90 (ms) | 15m: mean per event that hour (ms) | 24h: push p50 / p90 (ms) | 24h: mean per event that hour (ms) |
| --- | --- | --- | --- | --- |
| 1 h | 0.247 / 0.273 | 0.080 | 0.990 / 1.704 | 0.094 |
| 2 h | 0.246 / 0.254 | 0.076 | 5.157 / 6.565 | 0.224 |
| 4 h | 0.236 / 0.253 | 0.077 | 23.264 / 27.223 | 0.833 |
| 8 h | 0.253 / 0.277 | 0.088 | 106.068 / 113.689 | 3.473 |
| 12 h | 0.244 / 0.267 | 0.079 | 243.184 / 251.396 | 7.922 |

## Push decision latency, disk (/tmp, fsync per event), 360 events/hour, sparse: 12 test runs/hour, rest file reads

| Session length | 15m: push p50 / p90 (ms) | 15m: mean per event that hour (ms) | 24h: push p50 / p90 (ms) | 24h: mean per event that hour (ms) |
| --- | --- | --- | --- | --- |
| 1 h | 0.386 / 0.735 | 0.408 | 0.632 / 0.836 | 0.457 |
| 2 h | 0.391 / 0.407 | 0.414 | 1.238 / 1.354 | 0.491 |
| 4 h | 0.370 / 0.435 | 0.381 | 2.398 / 3.337 | 0.509 |
| 8 h | 0.445 / 0.723 | 0.462 | 8.208 / 8.874 | 0.783 |
| 12 h | 0.456 / 0.577 | 0.497 | 18.317 / 19.871 | 1.051 |

## Push decision latency, RAM (/dev/shm), 360 events/hour, sparse: 12 test runs/hour, rest file reads

| Session length | 15m: push p50 / p90 (ms) | 15m: mean per event that hour (ms) | 24h: push p50 / p90 (ms) | 24h: mean per event that hour (ms) |
| --- | --- | --- | --- | --- |
| 1 h | 0.110 / 0.127 | 0.094 | 0.184 / 0.234 | 0.099 |
| 2 h | 0.123 / 0.213 | 0.105 | 0.445 / 0.602 | 0.100 |
| 4 h | 0.200 / 0.206 | 0.155 | 1.969 / 2.172 | 0.154 |
| 8 h | 0.173 / 0.191 | 0.134 | 7.553 / 8.041 | 0.334 |
| 12 h | 0.189 / 0.201 | 0.121 | 17.421 / 17.970 | 0.660 |

