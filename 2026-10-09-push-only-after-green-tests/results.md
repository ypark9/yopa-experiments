# Run 2026-10-09T20:12:33-04:00 on Linux 6.12.94+ x86_64, 8 vCPU, rustc 1.99.0, dogwood-local-engine d2cba92
# /tmp filesystem: overlayfs; /dev/shm: tmpfs
# Revision after review: push policy now correlated on repo + tested commit (C); C0 = the uncorrelated policy from the AWS post, run on the same traces. Traces T10-T12 are new. Latency tables time the whole push submit() (persist + evaluate) and report the median / p90 of the last 10 pushes in each checkpoint hour.

## Verdict table

| Trace | What happens | Rule says | A stateless | B in-memory (repo+sha) | C Dogwood (correlated) | C0 Dogwood (AWS post policy, uncorrelated) |
| --- | --- | --- | --- | --- | --- | --- |
| T1 | tests fail, push 5s later | DENY | DENY | DENY | DENY | DENY |
| T2 | tests pass, push 5s later | ALLOW | ALLOW | ALLOW | ALLOW | ALLOW |
| T3 | tests pass, push 17 min later | DENY | ALLOW (wrong) | DENY | DENY | DENY |
| T4 | pass, then fail, push | DENY | ALLOW (wrong) | DENY | DENY | DENY |
| T5 | no test run, agent claims tests passed | DENY | ALLOW (wrong) | DENY | DENY | DENY |
| T6 | tests pass, harness restarts, push | ALLOW | ALLOW | DENY (wrong) | ALLOW | ALLOW |
| T7 | tests pass, owner re-runs install() with same policies, push | ALLOW | ALLOW | ALLOW | DENY (wrong) | DENY (wrong) |
| T8 | tests pass, owner widens push window 15m->30m via batch(Update), push | ALLOW | ALLOW | ALLOW | DENY (wrong) | DENY (wrong) |
| T9 | same as T8, then tests re-run and push | ALLOW | ALLOW | ALLOW | ALLOW | ALLOW |
| T10 | tests pass on repo A, push on repo B | DENY | ALLOW (wrong) | DENY | DENY | ALLOW (wrong) |
| T11 | tests pass on commit X, push commit Y (same repo) | DENY | ALLOW (wrong) | DENY | DENY | ALLOW (wrong) |
| T12 | tests pass on repo A, fail on repo B, push repo A | ALLOW | ALLOW | ALLOW | ALLOW | DENY (wrong) |

## Restart with the host clock stepped back

| Clock at reopen vs last stored event | Store opens? |
| --- | --- |
| 60 s behind | yes |
| 299 s behind | yes |
| 301 s behind | no: durable timestamp is ahead of the current clock beyond max_future_skew |
| 600 s behind | no: durable timestamp is ahead of the current clock beyond max_future_skew |

B in-memory gate: 42.3 ns per decision (1,000,000 decisions, 1000000 allowed)

## Push submit latency (persist + evaluate), correlated policy, disk (/tmp, fsync per event), 360 events/hour, dense: per hour 180 tests requests + 168 passing responses + 12 pushes

| Session length | 15m: push p50 / p90 (ms) | 15m: mean per event that hour (ms) | 24h: push p50 / p90 (ms) | 24h: mean per event that hour (ms) |
| --- | --- | --- | --- | --- |
| 1 h | 0.779 / 0.888 | 0.437 | 1.896 / 3.134 | 0.562 |
| 2 h | 0.777 / 1.151 | 0.406 | 8.163 / 9.556 | 0.673 |
| 4 h | 0.853 / 1.173 | 0.480 | 33.197 / 39.644 | 1.807 |
| 8 h | 0.734 / 0.962 | 0.524 | 143.905 / 170.434 | 5.453 |
| 12 h | 0.704 / 0.984 | 0.504 | 330.490 / 346.846 | 11.292 |

## Push submit latency (persist + evaluate), correlated policy, RAM (/dev/shm), 360 events/hour, dense: per hour 180 tests requests + 168 passing responses + 12 pushes

| Session length | 15m: push p50 / p90 (ms) | 15m: mean per event that hour (ms) | 24h: push p50 / p90 (ms) | 24h: mean per event that hour (ms) |
| --- | --- | --- | --- | --- |
| 1 h | 0.313 / 0.326 | 0.082 | 1.251 / 2.082 | 0.108 |
| 2 h | 0.334 / 0.339 | 0.089 | 7.421 / 8.847 | 0.288 |
| 4 h | 0.331 / 0.346 | 0.085 | 31.939 / 36.337 | 1.080 |
| 8 h | 0.314 / 0.327 | 0.086 | 141.405 / 149.206 | 4.662 |
| 12 h | 0.307 / 0.331 | 0.083 | 331.441 / 341.048 | 10.944 |

## Push submit latency (persist + evaluate), correlated policy, disk (/tmp, fsync per event), 360 events/hour, sparse: per hour 12 tests requests + 12 passing responses + 324 file reads + 12 pushes

| Session length | 15m: push p50 / p90 (ms) | 15m: mean per event that hour (ms) | 24h: push p50 / p90 (ms) | 24h: mean per event that hour (ms) |
| --- | --- | --- | --- | --- |
| 1 h | 0.535 / 0.652 | 0.519 | 0.603 / 1.092 | 0.464 |
| 2 h | 0.646 / 0.958 | 0.535 | 0.912 / 1.135 | 0.468 |
| 4 h | 0.475 / 0.596 | 0.609 | 2.751 / 3.344 | 0.537 |
| 8 h | 0.522 / 0.598 | 0.479 | 11.070 / 13.458 | 0.854 |
| 12 h | 0.535 / 0.728 | 0.580 | 23.732 / 24.980 | 1.483 |

## Push submit latency (persist + evaluate), correlated policy, RAM (/dev/shm), 360 events/hour, sparse: per hour 12 tests requests + 12 passing responses + 324 file reads + 12 pushes

| Session length | 15m: push p50 / p90 (ms) | 15m: mean per event that hour (ms) | 24h: push p50 / p90 (ms) | 24h: mean per event that hour (ms) |
| --- | --- | --- | --- | --- |
| 1 h | 0.134 / 0.139 | 0.092 | 0.229 / 0.433 | 0.111 |
| 2 h | 0.140 / 0.146 | 0.097 | 1.009 / 1.184 | 0.154 |
| 4 h | 0.140 / 0.171 | 0.099 | 2.355 / 2.677 | 0.164 |
| 8 h | 0.145 / 0.153 | 0.105 | 10.689 / 11.478 | 0.438 |
| 12 h | 0.131 / 0.143 | 0.091 | 22.022 / 23.327 | 0.843 |

## Push submit latency (persist + evaluate), uncorrelated policy (AWS post), disk (/tmp, fsync per event), 360 events/hour, dense: per hour 180 tests requests + 168 passing responses + 12 pushes

| Session length | 15m: push p50 / p90 (ms) | 15m: mean per event that hour (ms) | 24h: push p50 / p90 (ms) | 24h: mean per event that hour (ms) |
| --- | --- | --- | --- | --- |
| 1 h | 0.512 / 0.817 | 0.378 | 1.356 / 2.010 | 0.394 |
| 2 h | 0.721 / 0.792 | 0.525 | 5.906 / 7.138 | 0.582 |
| 4 h | 0.635 / 0.863 | 0.723 | 25.261 / 34.011 | 1.284 |
| 8 h | 0.705 / 0.755 | 0.444 | 115.464 / 121.110 | 4.300 |
| 12 h | 0.588 / 0.663 | 0.438 | 249.577 / 259.699 | 8.838 |

## Push submit latency (persist + evaluate), uncorrelated policy (AWS post), disk (/tmp, fsync per event), 360 events/hour, sparse: per hour 12 tests requests + 12 passing responses + 324 file reads + 12 pushes

| Session length | 15m: push p50 / p90 (ms) | 15m: mean per event that hour (ms) | 24h: push p50 / p90 (ms) | 24h: mean per event that hour (ms) |
| --- | --- | --- | --- | --- |
| 1 h | 0.391 / 0.594 | 0.365 | 0.538 / 0.907 | 0.416 |
| 2 h | 0.388 / 0.561 | 0.413 | 0.759 / 1.133 | 0.458 |
| 4 h | 0.506 / 0.599 | 0.495 | 2.351 / 2.989 | 0.460 |
| 8 h | 0.448 / 0.511 | 0.420 | 9.481 / 9.940 | 0.850 |
| 12 h | 0.434 / 0.603 | 0.452 | 20.106 / 28.648 | 1.174 |

