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

## Scale check: memory next to the LLM tokens of the same history (added 2026-10-09)

```bash
python3 scale.py results   # writes results/scale.csv; stdout saved as results/scale_stdout.txt
```

Puts the memory cost per session next to the LLM input-token cost of the history the agent
sends to the model, at 100,000 sessions per month. Still no AWS or model calls.

- Token rates, read 2026-10-09 from <https://aws.amazon.com/bedrock/pricing/> (Anthropic,
  on-demand, Global cross-region inference table, region selector US East (N. Virginia)),
  per 1M input tokens: Claude Sonnet 5.5 $2.00 (cache read $0.10), Claude Haiku 5.5 $0.10
  (cache read $0.01).
- 2.5 bytes per token, from Anthropic's models overview ("1M tokens is roughly ... 2.5M Unicode
  characters"). Context window 1M tokens (same page).
- Output tokens and the system prompt are ignored, so the token side is a lower bound and the
  memory share is an upper bound.
- Setups: `stateless` (fresh agent per request lists the whole session every turn),
  `in_process` (history listed once per session, kept in the agent; this is what the Strands
  integration does when the agent object lives for the session), `window_10` (memory and LLM
  both see the last 10 events).

Headline (50 turns, 2 events/turn, 30-day TTL, `results/scale_stdout.txt`):

- Against Claude Sonnet 5.5 at the full input price, memory is 0.01% to 0.62% of memory plus
  history tokens in every setup and size.
- Memory reaches several percent to tens of percent only when tokens are very cheap (Haiku 5.5,
  or cache reads) and events are small. The 12 KB minimum bills a 1 KB message as 12 KB, while
  tokens are billed on the real 1 KB.
- Every crossover where the new price passes the old one, except 1 KB events after about 200
  turns, happens on a turn whose full history would be over 1M tokens. An agent cannot send that
  history to the model, so it would be paying to read events it then drops.

## How the SDK loads history (read 2026-10-09)

- `aws/bedrock-agentcore-sdk-python` @ `99663b02a9227dcc87e85529d456685b77995561`,
  `src/bedrock_agentcore/memory/integrations/strands/session_manager.py`: `list_messages`
  (L756-797) lists events with `max_results = (limit + offset) if limit else
  MAX_FETCH_ALL_RESULTS` (L783), and `MAX_FETCH_ALL_RESULTS = 10000` (L49). No default window.
- `strands-agents/sdk-python` @ `afc3e059b1ff932fb8f86be2d444846aa3e2a06e`,
  `strands-py/src/strands/session/repository_session_manager.py`: `initialize` (L210) calls
  `list_messages` without a limit (L274-278) and restores `agent.messages` (L292).
  `append_message` (L80-97) only writes (`create_message`, L97); it does not read back.
- So with the Strands integration, the whole session is read once each time an agent is
  constructed. If a handler builds a new `Agent` per request, that is a full-history read per
  turn. If the agent object lives for the session, it is one read per session.
- `config.py` L94: `batch_size` defaults to 1, one event per message. With `batch_size > 1`,
  buffered messages are combined into a single `create_event` call (`session_manager.py`
  docstring around L1058), which is the lever against the 12 KB minimum.
