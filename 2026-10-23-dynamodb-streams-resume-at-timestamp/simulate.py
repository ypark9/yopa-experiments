"""Local model of the DOCUMENTED AT_TIMESTAMP rules (no AWS):
 - ApproximateCreationDateTime is floored to the second (StreamRecord docs)
 - AT_TIMESTAMP -> first record with ApproximateCreationDateTime >= T (GetShardIterator docs)
 - T older than trim horizon -> oldest untrimmed record, no error
 - T in the future -> ValidationException
A consumer crashes, then resumes using one of several checkpoint strategies.
We count records lost (never processed) and processed twice."""
import random, math, json
random.seed(20261023)
RATE = 20.0            # writes per second
DUR = 3600             # one hour of writes
recs, t = [], 1792770000.0
while t < 1792770000.0 + DUR:
    t += random.expovariate(RATE)
    recs.append({"seq": len(recs), "true": t, "approx": math.floor(t)})
def at_timestamp(T, now, trim_horizon):
    if T > now: raise ValueError("ValidationException: timestamp in the future")
    T = max(T, trim_horizon)
    return next((i for i, r in enumerate(recs) if r["approx"] >= T), len(recs))
def run(strategy, crash_idx, downtime_s, trim_horizon=0.0):
    last = recs[crash_idx]                     # last record fully processed
    now = last["true"] + downtime_s            # time the consumer comes back
    if strategy == "LATEST":
        start = next((i for i, r in enumerate(recs) if r["true"] > now), len(recs))
    elif strategy == "TRIM_HORIZON":
        start = next(i for i, r in enumerate(recs) if r["approx"] >= trim_horizon)
    elif strategy == "AT_TIMESTAMP(last approx)":
        start = at_timestamp(last["approx"], now, trim_horizon)
    elif strategy == "AT_TIMESTAMP(last approx + 1 ms)":
        start = at_timestamp(last["approx"] + 0.001, now, trim_horizon)
    elif strategy == "AT_TIMESTAMP(wall clock at checkpoint)":
        start = at_timestamp(last["true"] + 0.050, now, trim_horizon)  # checkpoint written 50 ms after processing
    elif strategy == "AFTER_SEQUENCE_NUMBER":
        start = crash_idx + 1
    lost = max(0, start - (crash_idx + 1))
    dup = max(0, (crash_idx + 1) - start)
    return lost, dup
strategies = ["LATEST", "TRIM_HORIZON", "AT_TIMESTAMP(last approx)", "AT_TIMESTAMP(last approx + 1 ms)",
              "AT_TIMESTAMP(wall clock at checkpoint)", "AFTER_SEQUENCE_NUMBER"]
crashes = random.sample(range(1000, len(recs) - 3000), 200)
rows = []
for s in strategies:
    L = [run(s, c, downtime_s=60) for c in crashes]
    lost = [l for l, _ in L]; dup = [d for _, d in L]
    rows.append({"strategy": s, "crashes": len(L),
                 "runs_with_loss": sum(1 for x in lost if x), "mean_lost": round(sum(lost)/len(L), 1), "max_lost": max(lost),
                 "runs_with_dups": sum(1 for x in dup if x), "mean_dup": round(sum(dup)/len(L), 1), "max_dup": max(dup)})
# worked example: one crash, print the neighbourhood
c = crashes[0]; last = recs[c]
same_sec = [r for r in recs if r["approx"] == last["approx"]]
example = {"last_processed": last, "records_in_same_second": len(same_sec),
           "after_last_in_same_second": sum(1 for r in same_sec if r["seq"] > last["seq"]),
           "before_last_in_same_second": sum(1 for r in same_sec if r["seq"] < last["seq"])}
# stale checkpoint older than trim horizon: silent fallback
th = recs[0]["approx"] + 1800
start = at_timestamp(recs[100]["approx"], recs[-1]["true"], th)
stale = {"checkpoint_T": recs[100]["approx"], "trim_horizon": th, "first_record_returned_approx": recs[start]["approx"],
         "records_between_checkpoint_and_horizon_lost": start - 100, "error_raised": False}
try: at_timestamp(recs[-1]["true"] + 2, recs[-1]["true"], 0); fut = "no error"
except ValueError as e: fut = str(e)
print(json.dumps({"records": len(recs), "rate_per_s": RATE, "downtime_s": 60, "table": rows,
                  "example": example, "stale_checkpoint": stale, "future_timestamp": fut}, indent=1))
