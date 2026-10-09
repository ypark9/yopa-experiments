#!/usr/bin/env python3
"""Cost model for Amazon Bedrock AgentCore short-term memory, old vs new pricing.

No AWS calls. Every rate below is copied from the AgentCore pricing page
(https://aws.amazon.com/bedrock/agentcore/pricing/, read 2026-10-09):

  old (through 2026-10-05): ingestion $0.25 per 1,000 new events, nothing else
  new (as of 2026-10-06):   ingestion $1.00 per GB, retrieval $0.20 per GB,
                            storage $0.10 per GB-month
                            ingestion and retrieval bill each event at
                            min 12 KB / max 64 KB; storage bills actual size,
                            prorated hourly over the event's TTL

Units: decimal (1 KB = 1,000 bytes, 1 GB = 1e9 bytes). That is what AWS's own
example uses ("100,000 events x 12 KB = 1.2 GB").
Month for storage proration: 730 hours (AWS's usual billing month).
"""
import csv, json, sys
from dataclasses import dataclass

KB = 1_000
GB = 1_000_000_000
OLD_PER_EVENT = 0.25 / 1000
NEW_INGEST_PER_GB = 1.00
NEW_RETRIEVE_PER_GB = 0.20
NEW_STORAGE_PER_GB_MONTH = 0.10
MIN_BILL, MAX_BILL = 12 * KB, 64 * KB
HOURS_PER_MONTH = 730


def billable(size_bytes):
    return min(max(size_bytes, MIN_BILL), MAX_BILL)


def ingest_cost(size):
    return billable(size) / GB * NEW_INGEST_PER_GB


def retrieve_cost(size):
    return billable(size) / GB * NEW_RETRIEVE_PER_GB


def storage_cost(size, ttl_days):
    return size / GB * NEW_STORAGE_PER_GB_MONTH * (ttl_days * 24 / HOURS_PER_MONTH)


def aws_example():
    """AWS's 'Personalized Coding Assistant' example, short-term part only."""
    n, size = 100_000, 3 * KB
    ing = n * ingest_cost(size)
    ret = n * retrieve_cost(size)          # each event retrieved once
    sto_30d = n * storage_cost(size, 30)   # 30-day TTL
    sto_1mo = n * size / GB * NEW_STORAGE_PER_GB_MONTH  # "held for one month"
    return {"ingestion": ing, "retrieval": ret, "storage_30d_ttl_730h_month": sto_30d,
            "storage_one_full_month": sto_1mo,
            "aws_published": {"ingestion": 1.20, "retrieval": 0.24, "storage": 0.03}}


@dataclass
class Pattern:
    name: str
    window: int | None  # None = reload everything; 0 = no read-back; k = last k events


PATTERNS = [
    Pattern("full_history", None),
    Pattern("last_40", 40),
    Pattern("last_10", 10),
    Pattern("no_readback", 0),
]


def session_cost(turns, events_per_turn, size, ttl_days, pattern):
    """One session: each turn first reads per the pattern, then writes its events."""
    stored = 0
    retrievals = 0
    for _ in range(turns):
        if pattern.window is None:
            retrievals += stored
        else:
            retrievals += min(pattern.window, stored)
        stored += events_per_turn
    n_events = turns * events_per_turn
    new = {
        "ingestion": n_events * ingest_cost(size),
        "retrieval": retrievals * retrieve_cost(size),
        "storage": n_events * storage_cost(size, ttl_days),
    }
    new["total"] = sum(new.values())
    old = n_events * OLD_PER_EVENT
    return old, new, retrievals


def crossover_turns(events_per_turn, size, ttl_days, pattern, max_turns=2000):
    for t in range(1, max_turns + 1):
        old, new, _ = session_cost(t, events_per_turn, size, ttl_days, pattern)
        if new["total"] > old:
            return t
    return None


def main(outdir):
    ex = aws_example()
    print("== AWS pricing-page example (100,000 x 3 KB events, read once, 30-day TTL)")
    for k in ("ingestion", "retrieval", "storage_30d_ttl_730h_month", "storage_one_full_month"):
        print(f"  {k:28s} ${ex[k]:.4f}")
    print(f"  published                    {ex['aws_published']}")

    print("\n== Per-event unit costs (USD)")
    print(f"  old flat rate per event          {OLD_PER_EVENT:.7f}")
    for s in (1 * KB, 12 * KB, 64 * KB, 256 * KB):
        print(f"  {s//KB:>4} KB  ingest {ingest_cost(s):.7f}  retrieve {retrieve_cost(s):.7f}  "
              f"store 30d {storage_cost(s, 30):.7f}  store 365d {storage_cost(s, 365):.7f}")

    sizes = [1 * KB, 12 * KB, 64 * KB, 256 * KB]
    ttls = [7, 30, 90, 365]
    epts = [2, 4]  # events per turn: user+assistant, or user+assistant+2 tool events
    rows = []
    for ept in epts:
        for size in sizes:
            for ttl in ttls:
                for p in PATTERNS:
                    x = crossover_turns(ept, size, ttl, p)
                    o, n, r = session_cost(50, ept, size, ttl, p)
                    rows.append({
                        "events_per_turn": ept, "event_kb": size // KB, "ttl_days": ttl,
                        "pattern": p.name, "crossover_turn": x if x is not None else "",
                        "turns50_old_usd": round(o, 6), "turns50_new_usd": round(n["total"], 6),
                        "turns50_new_ingest": round(n["ingestion"], 6),
                        "turns50_new_retrieve": round(n["retrieval"], 6),
                        "turns50_new_storage": round(n["storage"], 6),
                        "turns50_new_over_old": round(n["total"] / o, 4),
                        "turns50_retrievals": r,
                    })
    with open(f"{outdir}/sweep.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader(); w.writerows(rows)

    print("\n== Crossover turn (first session length where new > old); '-' = none up to 2000 turns")
    for ept in epts:
        print(f"\n-- {ept} events per turn, TTL 30 days")
        print(f"  {'event size':>10} | " + " | ".join(f"{p.name:>12}" for p in PATTERNS))
        for size in sizes:
            cells = []
            for p in PATTERNS:
                x = crossover_turns(ept, size, 30, p)
                cells.append(f"{(x if x else '-'):>12}")
            print(f"  {str(size//KB)+' KB':>10} | " + " | ".join(cells))

    print("\n-- TTL effect, 2 events per turn, no read-back (storage only matters here)")
    for size in sizes:
        cells = []
        for ttl in ttls:
            o, n, _ = session_cost(50, 2, size, ttl, PATTERNS[3])
            cells.append(f"TTL {ttl:>3}d new/old {n['total']/o:6.3f}")
        print(f"  {size//KB:>4} KB  " + "  ".join(cells))

    print("\n-- 50-turn session, 2 events/turn, 30-day TTL: cost in USD per session")
    for size in (12 * KB, 64 * KB):
        for p in PATTERNS:
            o, n, r = session_cost(50, 2, size, 30, p)
            print(f"  {size//KB:>3} KB {p.name:>12}: old {o:.5f}  new {n['total']:.5f} "
                  f"(ingest {n['ingestion']:.5f}, retrieve {n['retrieval']:.5f}, store {n['storage']:.6f})"
                  f"  retrievals {r}")

    json.dump({"aws_example": ex}, open(f"{outdir}/aws_example.json", "w"), indent=1)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "results")
