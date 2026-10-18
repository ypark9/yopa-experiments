| case | group | what | durablelint | outcome over all trials | golden signature would fail |
|---|---|---|---|---|---|
| A01 | A | time.Now() outside a step, used as idempotency key | yes (1: durablenondeterminism) | silent 60 (n=60) | 0/60 |
| A02 | A | rand key outside a step | yes (1: durablenondeterminism) | silent 60 (n=60) | 0/60 |
| A03 | A | random branch adds a step before the wait | yes (1: durablenondeterminism) | nde 43, ok 17 (n=60) | 47/60 |
| A04 | A | range over a map creates steps | yes (1: durablenondeterminism) | nde 31, ok 29 (n=60) | 22/60 |
| A05 | A | map keys copied to an unsorted slice, then steps | no | nde 41, ok 19 (n=60) | 31/60 |
| A06 | A | clock read inside a helper without a Context | no | silent 60 (n=60) | 0/60 |
| A07 | A | ctx.RequestID() used as a key | yes (1: durablenondeterminism) | ok 60 (n=60) | 0/60 |
| A08 | A | plain goroutines call Step on the parent context | yes (2: durablegoroutine) | first-run-error:Error 60 (n=60) | 0/60 |
| A09 | A | control: key in a step, ExecutionStartTime, sorted keys | no | ok 60 (n=60) | 0/60 |
| B01 | B | rename a completed step | no | nde 60 (n=60) | 60/60 |
| B02 | B | swap two completed steps | no | nde 60 (n=60) | 60/60 |
| B03 | B | insert a step before the wait | no | nde 60 (n=60) | 60/60 |
| B04 | B | insert a step after the wait | no | ok 60 (n=60) | 60/60 |
| B05 | B | remove a completed step | no | nde 60 (n=60) | 60/60 |
| B06 | B | remove a step that has not run | no | ok 60 (n=60) | 60/60 |
| B07 | B | change a completed step's return type | no | error:SerdesError 60 (n=60) | 0/60 |
| B08 | B | rename a JSON tag in a completed step's result | no | silent 60 (n=60) | 0/60 |
| B09 | B | change the logic inside a completed step | no | silent 60 (n=60) | 0/60 |
| B10 | B | change the wait duration | no | ok 60 (n=60) | 0/60 |
| B11 | B | rename the wait the execution is paused on | no | nde 60 (n=60) | 60/60 |
| B12 | B | wrap a completed step in a child context | no | nde 60 (n=60) | 60/60 |
| B13 | B | add a field to a completed step's result | no | silent 60 (n=60) | 0/60 |
| B14 | B | env var read between operations flips while paused | no | nde 60 (n=60) | 0/60 |

Per run (verdict counts out of the trials in that run):

- A03 run 1: nde 17, ok 3
- A03 run 2: nde 11, ok 9
- A03 run 3: nde 15, ok 5
- A04 run 1: nde 12, ok 8
- A04 run 2: nde 14, ok 6
- A04 run 3: nde 5, ok 15
- A05 run 1: nde 13, ok 7
- A05 run 2: nde 14, ok 6
- A05 run 3: nde 14, ok 6

Verdicts: ok = succeeded and output consistent; silent = succeeded but output inconsistent (A: keys/totals disagree with what invocation 1 checkpointed; B: differs from a fresh run of the new code); nde = failed with NonDeterministicExecutionError on replay; error:<type> = failed with another error on replay; first-run-error:<type> = failed before any replay.
