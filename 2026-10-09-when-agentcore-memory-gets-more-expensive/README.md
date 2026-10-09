# When does AgentCore short-term memory get more expensive?

Code and raw results for the yopa.page post
`2026-10-09-when-agentcore-memory-gets-more-expensive` (draft, not yet published).

**This experiment makes no AWS calls, creates nothing, and costs nothing.** It is arithmetic over
the rates published on the [AgentCore pricing page](https://aws.amazon.com/bedrock/agentcore/pricing/)
(read 2026-10-09), replayed over synthetic agent sessions.

## What it models

| | Through 2026-10-05 | As of 2026-10-06 |
|---|---|---|
| Ingestion | $0.25 per 1,000 new events | $1.00 per GB, each event billed at 12 KB min / 64 KB max |
| Retrieval | (no separate line) | $0.20 per GB, same 12 KB / 64 KB clamp per event |
| Storage | (no separate line) | $0.10 per GB-month on actual size, prorated hourly over the TTL |

A session is `turns` turns. Each turn reads back from short-term memory according to a pattern,
then writes `events_per_turn` events of one size. Patterns:

- `full_history`: reload every event in the session each turn
- `last_40`, `last_10`: read only the most recent K events
- `no_readback`: write only

`crossover_turn` is the first session length at which the new pricing costs more than the old
flat rate for the same session.

## Run

```bash
python3 model.py results
```

Python 3.10+, standard library only.

## Results (2026-10-09)

See `results/stdout.txt` and `results/sweep.csv` (128 rows: 2 events-per-turn values x 4 sizes x
4 TTLs x 4 patterns). Headline numbers:

- AWS's own example reproduces: ingestion $1.20, retrieval $0.24, storage $0.0296 with a
  730-hour month ($0.03 if the 30-day TTL is counted as one full month, as the page does).
- Read-once or write-only sessions are about 5% of the old cost for small events.
- Reloading full history every turn crosses the old cost at **turn 199-200 for events up to
  12 KB** and at **turn 30 for 64 KB events** (27 for 256 KB).
- A last-10 window never crosses in this sweep. A last-40 window crosses at turn 36 for 64 KB
  events when a turn writes 2 events, and does not cross when a turn writes 4.
- Write-only 256 KB events with a 365-day TTL cost 1.49x the old rate: storage is billed on
  actual size, while ingestion is capped at 64 KB.

## What this does not prove

- It does not read any real account's event sizes or read patterns. Doing that would itself
  make billed retrieval calls.
- It assumes each event returned by a read is billed as one retrieval with the 12 KB minimum.
  The pricing page says "each retrieval is billed using the same 12 KB minimum and 64 KB
  maximum per event"; no API-level billing document was checked.
- It ignores long-term memory, the 2026-10-06 storage exemption for older events, and the
  credit AWS applies through 2026-12-31 to accounts that would pay more.
- Decimal units (1 GB = 1e9 bytes) are inferred from AWS's example (12 KB x 100,000 = 1.2 GB).
