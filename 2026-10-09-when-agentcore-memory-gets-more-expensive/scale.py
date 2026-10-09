#!/usr/bin/env python3
"""Scale check: AgentCore short-term memory cost per session next to the LLM
input-token cost of the same history. No AWS calls, no model calls.

Memory side: model.py (new per-GB pricing, 12 KB / 64 KB clamp, same assumptions).

Token side, rates read 2026-10-09 from https://aws.amazon.com/bedrock/pricing/
(Anthropic, On-Demand, Global cross-region inference table, region selector at
US East (N. Virginia)); per 1M input tokens:
  Claude Sonnet 5.5: input $2.00, cache read $0.10
  Claude Haiku 5.5:  input $0.10, cache read $0.01
Output tokens are ignored, so the token side is a lower bound and the memory
share computed here is an upper bound.

Bytes per token: 2.5, from Anthropic's models overview ("1M tokens is roughly
... 2.5M Unicode characters on the current tokenizer"), treating 1 char = 1 byte.
Context window 1M tokens (same page); calls above that are flagged.

Two ways an agent can hold history:
  stateless   : a fresh agent per request lists the whole session from memory
                every turn (model.py full_history), and the LLM sees all of it.
  in_process  : Strands + AgentCoreMemorySessionManager lists the session once
                at agent init and keeps history in agent.messages; within one
                live session nothing is re-read (memory = model.py no_readback),
                but the LLM still sees the whole history every turn.
  window_10   : both memory and LLM use the last 10 events (model.py last_10).
"""
import csv, sys
from model import session_cost, crossover_turns, PATTERNS, Pattern, KB

MODELS = {
    "claude-sonnet-5.5": {"input": 2.00, "cache_read": 0.10},
    "claude-haiku-5.5": {"input": 0.10, "cache_read": 0.01},
}
BYTES_PER_TOKEN = 2.5
CONTEXT_TOKENS = 1_000_000
SESSIONS_PER_MONTH = 100_000

SETUPS = {
    "stateless": (Pattern("full_history", None), None),
    "in_process": (Pattern("no_readback", 0), None),
    "window_10": (Pattern("last_10", 10), 10),
}


def llm_history_tokens(turns, ept, size, window):
    """Total history tokens sent to the LLM over a session, and the peak call."""
    total = peak = 0
    stored = 0
    for _ in range(turns):
        seen = stored if window is None else min(window, stored)
        tok = seen * size / BYTES_PER_TOKEN
        total += tok
        peak = max(peak, tok)
        stored += ept
    return total, peak


def main(outdir):
    rows = []
    for turns in (10, 20, 50):
        for ept in (2, 4):
            for size_kb in (1, 4, 12, 64):
                size = size_kb * KB
                for setup, (pat, window) in SETUPS.items():
                    old, new, _ = session_cost(turns, ept, size, 30, pat)
                    tok, peak = llm_history_tokens(turns, ept, size, window)
                    for mname, r in MODELS.items():
                        for price_kind in ("input", "cache_read"):
                            llm = tok / 1e6 * r[price_kind]
                            mem = new["total"]
                            rows.append({
                                "turns": turns, "events_per_turn": ept, "event_kb": size_kb,
                                "setup": setup, "model": mname, "token_price": price_kind,
                                "memory_new_usd": round(mem, 6), "memory_old_usd": round(old, 6),
                                "llm_history_input_usd": round(llm, 6),
                                "memory_share_new": round(mem / (mem + llm), 5) if mem + llm else 0,
                                "memory_share_old": round(old / (old + llm), 5) if old + llm else 0,
                                "history_tokens": int(tok), "peak_call_tokens": int(peak),
                                "over_context": peak > CONTEXT_TOKENS,
                                "monthly_memory_new_usd": round(mem * SESSIONS_PER_MONTH, 2),
                                "monthly_memory_old_usd": round(old * SESSIONS_PER_MONTH, 2),
                                "monthly_llm_history_usd": round(llm * SESSIONS_PER_MONTH, 2),
                            })
    with open(f"{outdir}/scale.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader(); w.writerows(rows)

    def pick(**k):
        return [r for r in rows if all(r[a] == b for a, b in k.items())]

    print("== 50-turn session, 2 events/turn, 30-day TTL, 100,000 sessions/month")
    print("   memory share = memory / (memory + LLM history input), output tokens ignored")
    for setup in SETUPS:
        print(f"\n-- {setup}")
        print(f"  {'KB':>3} {'model':>18} {'price':>10} | {'mem new $/mo':>12} {'mem old $/mo':>12} "
              f"{'LLM hist $/mo':>13} | {'share new':>9} {'share old':>9} | peak tok")
        for size_kb in (1, 4, 12, 64):
            for r in pick(turns=50, events_per_turn=2, event_kb=size_kb, setup=setup):
                flag = " OVER 1M" if r["over_context"] else ""
                print(f"  {size_kb:>3} {r['model']:>18} {r['token_price']:>10} | "
                      f"{r['monthly_memory_new_usd']:>12,.0f} {r['monthly_memory_old_usd']:>12,.0f} "
                      f"{r['monthly_llm_history_usd']:>13,.0f} | {r['memory_share_new']:>8.2%} "
                      f"{r['memory_share_old']:>8.2%} | {r['peak_call_tokens']:,}{flag}")

    print("\n== Max memory share (new pricing) per setup, over all rows within 1M context")
    for setup in SETUPS:
        for kind in ("input", "cache_read"):
            ok = [r for r in rows if r["setup"] == setup and r["token_price"] == kind and not r["over_context"]]
            m = max(ok, key=lambda r: r["memory_share_new"])
            print(f"  {setup:>10} {kind:>10}: {m['memory_share_new']:.2%} "
                  f"({m['model']}, {m['event_kb']} KB, {m['turns']} turns, {m['events_per_turn']} ev/turn)")

    print("\n== Does the crossover (new > old) happen inside a 1M-token context?")
    print("   peak = history tokens the LLM would see on the crossover turn if it read what memory returned")
    for ept in (2, 4):
        for size_kb in (1, 12, 64, 256):
            for p in PATTERNS:
                x = crossover_turns(ept, size_kb * KB, 30, p)
                if x is None:
                    continue
                seen = (x - 1) * ept if p.window is None else min(p.window, (x - 1) * ept)
                peak = seen * size_kb * KB / BYTES_PER_TOKEN
                print(f"  {ept} ev/turn {size_kb:>3} KB {p.name:>12}: crossover turn {x:>4}, "
                      f"peak {peak:>12,.0f} tokens {'OVER 1M' if peak > CONTEXT_TOKENS else 'fits'}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "results")
